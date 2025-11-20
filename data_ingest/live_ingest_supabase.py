# data_ingest/live_ingest_supabase.py
"""
Fetch live threat intelligence feeds, enrich with OG images, and persist to Supabase.

Responsibilities:
- Pull multiple cybersecurity RSS feeds.
- Extract clean metadata (title, summary, link, published_at, source_name).
- Resolve OG/Twitter preview images, upload to Supabase Storage, capture public URL.
- Persist article metadata into Supabase `articles` table via UPSERT on unique link.
- Extract lightweight IOCs (IP/domain/CVE) and upsert into Supabase `iocs` table.
- Upload the raw JSON batch to Supabase storage for traceability (no local disk writes).
"""

from __future__ import annotations

import hashlib
import io
import json
import mimetypes
import os
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

try:
    from supabase import create_client
except Exception as exc:  # pragma: no cover - handled at runtime
    raise SystemExit(
        "supabase package not found. Install dependencies first: pip install supabase"
    ) from exc

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "raw-feeds")
SUPABASE_IMAGE_BUCKET = os.getenv("SUPABASE_IMAGE_BUCKET", "article-thumbnails")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit(
        "Missing Supabase credentials. Ensure SUPABASE_URL and SUPABASE_KEY are set."
    )

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
storage = supabase.storage.from_(SUPABASE_BUCKET)
image_storage = supabase.storage.from_(SUPABASE_IMAGE_BUCKET)

DEFAULT_IMAGE_URL = os.getenv(
    "DEFAULT_ARTICLE_IMAGE",
    "https://placehold.co/600x360/0f172a/ffffff?text=AI-CTI",
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

FEEDS: Dict[str, Dict[str, str]] = {
    "https://threatpost.com/feed/": {"name": "ThreatPost"},
    "https://www.bleepingcomputer.com/feed/": {"name": "BleepingComputer"},
    "https://feeds.feedburner.com/TheHackersNews": {"name": "The Hacker News"},
    "https://www.darkreading.com/rss.xml": {"name": "Dark Reading"},
    "https://www.csoonline.com/index.rss": {"name": "CSO Online"},
    "https://www.securityweek.com/feed/": {"name": "SecurityWeek"},
    "https://www.infosecurity-magazine.com/rss/news/": {"name": "Infosecurity Magazine"},
    "https://www.kaspersky.com/blog/feed/": {"name": "Securelist"},
    "https://www.scmagazine.com/home/feed": {"name": "SC Magazine"},
}

# Cybersecurity keywords to filter articles
CYBERSEC_KEYWORDS = {
    "security", "cyber", "threat", "attack", "breach", "vulnerability", "malware", "ransomware",
    "phishing", "hack", "exploit", "cve", "zero-day", "data leak", "incident", "compromise",
    "ioc", "indicator", "apt", "botnet", "trojan", "backdoor", "ddos", "sql injection",
    "xss", "firewall", "encryption", "cert", "advisory", "alert", "patch", "update",
    "critical", "severity", "cisa", "msrc", "mitre", "tactics", "techniques", "framework"
}

# Exclusion keywords (non-security topics) - STRICT FILTERING
EXCLUDE_KEYWORDS = {
    "phone", "smartphone", "galaxy", "iphone", "android", "oneplus", "samsung", "review",
    "camera", "battery", "display", "specs", "unboxing", "comparison", "flagship",
    "holiday", "shopping", "deal", "sale", "price", "discount", "tested", "verdict",
    "trip", "travel", "photo", "photos", "six flags", "holiday season", "spend money",
    "hard-earned", "dirty", "webinar", "event", "online event", "explore", "join us",
    "tablet", "amazon", "bang-for-buck", "popular tablets", "readers bought", "older model",
    "windows sucks", "how to fix", "marketing tool", "agentic os", "task manager"
}

ipv4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
domain = re.compile(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b")
cve = re.compile(r"(CVE-\d{4}-\d{4,7})", re.I)


def _clean_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return " ".join(value.replace("\n", " ").split())


def _is_cybersecurity_article(title: str, description: str) -> bool:
    """Filter articles to only include cybersecurity-related content - STRICT MODE."""
    text = f"{title} {description}".lower()
    
    # STRICT: Exclude if contains non-security keywords (immediate rejection)
    for exclude in EXCLUDE_KEYWORDS:
        if exclude in text:
            return False
    
    # STRICT: Must contain at least 2 cybersecurity keywords (not just 1)
    keyword_count = 0
    for keyword in CYBERSEC_KEYWORDS:
        if keyword in text:
            keyword_count += 1
            if keyword_count >= 2:  # Require at least 2 matches
                return True
    
    # If less than 2 keywords match, exclude it
    return False


def _parse_datetime(entry) -> str:
    for key in ("published", "updated", "created"):
        value = entry.get(key)
        if not value:
            continue
        try:
            parsed = parsedate_to_datetime(value)
            if not parsed.tzinfo:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat()
        except Exception:
            continue
    return datetime.now(tz=timezone.utc).isoformat()


def _resolve_source_name(url: str, default: str) -> str:
    try:
        netloc = urlparse(url).netloc
        return netloc.replace("www.", "") if netloc else default
    except Exception:
        return default


def _get_screenshot_url(article_url: str) -> Optional[str]:
    """Get screenshot URL using screenshot API service as fallback"""
    if not article_url:
        return None
    
    print(f"[screenshot] Attempting to get screenshot for: {article_url[:80]}")
    
    # Method 1: Try microlink.io screenshot API (free, no API key required)
    try:
        microlink_url = f"https://api.microlink.io/?url={requests.utils.quote(article_url)}&screenshot=true&viewport.width=1200&viewport.height=630"
        print(f"[screenshot] Trying microlink.io: {microlink_url[:100]}")
        resp = requests.get(microlink_url, timeout=15, headers=HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            screenshot_url = data.get("data", {}).get("screenshot", {}).get("url")
            if screenshot_url and screenshot_url.startswith("http"):
                print(f"[screenshot] ✓ Got screenshot URL from microlink: {screenshot_url[:80]}")
                # Verify the screenshot URL works
                try:
                    verify_resp = requests.head(screenshot_url, timeout=5, allow_redirects=True)
                    if verify_resp.status_code == 200:
                        return screenshot_url
                    else:
                        print(f"[screenshot] ✗ Screenshot URL returned {verify_resp.status_code}")
                except Exception as verify_err:
                    print(f"[screenshot] ✗ Could not verify screenshot URL: {verify_err}")
    except Exception as exc:
        print(f"[screenshot] microlink.io failed: {exc}")
    
    # Method 2: Try screenshotapi.net (free tier, but may require token)
    try:
        screenshot_api_key = os.getenv("SCREENSHOT_API_KEY", "free")
        screenshot_api2 = f"https://shot.screenshotapi.net/screenshot?token={screenshot_api_key}&url={requests.utils.quote(article_url)}&width=1200&height=630&output=image&file_type=png"
        print(f"[screenshot] Trying screenshotapi.net: {screenshot_api2[:100]}")
        resp2 = requests.get(screenshot_api2, timeout=15, allow_redirects=True)
        if resp2.status_code == 200:
            # screenshotapi.net returns the image directly or a redirect
            final_url = resp2.url if resp2.url != screenshot_api2 else screenshot_api2
            print(f"[screenshot] ✓ Got screenshot from screenshotapi.net: {final_url[:80]}")
            return final_url
    except Exception as exc:
        print(f"[screenshot] screenshotapi.net failed: {exc}")
    
    # Method 3: Try htmlcsstoimage.com (free tier available)
    try:
        htmlcsstoimage_api_key = os.getenv("HTMLCSSTOIMAGE_API_KEY")
        if htmlcsstoimage_api_key:
            htmlcss_url = f"https://hcti.io/v1/image?url={requests.utils.quote(article_url)}"
            resp3 = requests.post(htmlcss_url, auth=(htmlcsstoimage_api_key, ''), timeout=15)
            if resp3.status_code == 200:
                data3 = resp3.json()
                screenshot_url3 = data3.get("url")
                if screenshot_url3:
                    print(f"[screenshot] ✓ Got screenshot from htmlcsstoimage: {screenshot_url3[:80]}")
                    return screenshot_url3
    except Exception as exc:
        print(f"[screenshot] htmlcsstoimage failed: {exc}")
    
    print(f"[screenshot] ✗ All screenshot services failed for {article_url[:60]}")
    return None


def _extract_image_url(article_url: str) -> Optional[str]:
    try:
        resp = requests.get(article_url, timeout=12, headers=HEADERS, allow_redirects=True)
        resp.raise_for_status()
    except Exception as exc:
        print(f"[image] fetch failed for {article_url}: {exc}")
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    meta_selectors = [
        ("meta", {"property": "og:image"}),
        ("meta", {"name": "og:image"}),
        ("meta", {"property": "twitter:image"}),
        ("meta", {"name": "twitter:image"}),
        ("meta", {"property": "og:image:url"}),
    ]
    for tag_name, attrs in meta_selectors:
        tag = soup.find(tag_name, attrs=attrs)
        if tag and tag.get("content"):
            url = tag["content"].strip()
            if url.startswith("//"):
                parsed = urlparse(article_url)
                return f"{parsed.scheme}:{url}"
            if url.startswith("http"):
                return url
    return None


def _get_public_url(client, key: str) -> Optional[str]:
    """Get public URL from Supabase storage bucket."""
    try:
        # Clean key - remove any leading slashes or subdirectories
        clean_key = key.lstrip("/").split("/")[-1]  # Get just filename
        print(f"[image] _get_public_url called with key='{key}', clean_key='{clean_key}'")
        
        supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        print(f"[image] SUPABASE_URL: {supabase_url[:50] if supabase_url else 'NOT SET'}")
        print(f"[image] SUPABASE_IMAGE_BUCKET: {SUPABASE_IMAGE_BUCKET}")
        
        # Method 1: Construct URL manually (most reliable)
        # Format: https://{project_ref}.supabase.co/storage/v1/object/public/{bucket}/{key}
        if supabase_url and SUPABASE_IMAGE_BUCKET:
            try:
                from urllib.parse import quote
                # URL encode the key in case it has special characters
                encoded_key = quote(clean_key, safe='')
                public_url = f"{supabase_url}/storage/v1/object/public/{SUPABASE_IMAGE_BUCKET}/{encoded_key}"
                print(f"[image] Constructed manual URL: {public_url}")
                
                # Verify it works
                try:
                    test_resp = requests.head(public_url, timeout=8, allow_redirects=True)
                    print(f"[image] Manual URL HEAD request returned: {test_resp.status_code}")
                    if test_resp.status_code == 200:
                        print(f"[image] ✓✓✓ Manual URL verified and working!")
                        return public_url
                    elif test_resp.status_code == 404:
                        print(f"[image] ✗ Manual URL returned 404 - file might not exist or bucket not public")
                        # Try with GET to see if it's a different issue
                        try:
                            get_resp = requests.get(public_url, timeout=8, allow_redirects=True)
                            print(f"[image] GET request returned: {get_resp.status_code}")
                            if get_resp.status_code == 200:
                                print(f"[image] ✓ GET works, returning URL anyway")
                                return public_url
                        except:
                            pass
                    else:
                        print(f"[image] Manual URL returned {test_resp.status_code}")
                except Exception as verify_err:
                    print(f"[image] Could not verify manual URL: {verify_err}")
                    # Return anyway - might work on frontend
                    print(f"[image] Returning URL anyway despite verification error")
                    return public_url
            except Exception as const_exc:
                print(f"[image] URL construction failed: {const_exc}")
                import traceback
                traceback.print_exc()
        
        # Method 2: Try the get_public_url method (fallback)
        try:
            result = client.get_public_url(clean_key)
            print(f"[image] get_public_url API returned: {type(result)}")
            if isinstance(result, dict):
                url = result.get("publicUrl") or result.get("publicURL") or result.get("public_url")
                if url and url.startswith("http"):
                    print(f"[image] Got public URL from API (dict): {url[:80]}")
                    # Verify URL works
                    try:
                        test_resp = requests.head(url, timeout=8, allow_redirects=True)
                        if test_resp.status_code == 200:
                            return url
                        else:
                            print(f"[image] API URL returned {test_resp.status_code}")
                    except:
                        print(f"[image] Could not verify API URL")
            if isinstance(result, str) and result.startswith("http"):
                print(f"[image] Got public URL from API (string): {result[:80]}")
                try:
                    test_resp = requests.head(result, timeout=8, allow_redirects=True)
                    if test_resp.status_code == 200:
                        return result
                except:
                    pass
        except Exception as api_exc:
            print(f"[image] get_public_url API method failed: {api_exc}")
        
        print(f"[image] ✗✗✗ Could not generate working public URL for {key}")
        return None
    except Exception as exc:
        print(f"[image] get_public_url failed for {key}: {exc}")
        import traceback
        traceback.print_exc()
        return None


def _upload_image_to_supabase(image_url: str) -> Optional[str]:
    if not image_url:
        return None
    file_hash = hashlib.sha256(image_url.encode("utf-8")).hexdigest()[:16]
    
    # Ensure key has no slashes or subdirectories - flat structure only
    file_hash = file_hash.replace("/", "").replace("\\", "")
    
    # Try common extensions to find existing file
    common_extensions = [".jpg", ".jpeg", ".png", ".webp", ".gif"]
    for ext in common_extensions:
        key_with_ext = f"{file_hash}{ext}"
        existing_url = _get_public_url(image_storage, key_with_ext)
        if existing_url:
            # CRITICAL: Verify the URL actually works by checking if it's accessible
            try:
                test_resp = requests.head(existing_url, timeout=5, allow_redirects=True)
                if test_resp.status_code == 200:
                    print(f"[image] ✓ Verified existing thumbnail works: {existing_url}")
                    return existing_url
                else:
                    print(f"[image] ✗ Existing URL returned {test_resp.status_code}, URL: {existing_url[:100]}")
                    # Try clean URL without any subdirectories
                    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
                    if supabase_url:
                        clean_key = key_with_ext.lstrip("/").split("/")[-1]
                        clean_url = f"{supabase_url}/storage/v1/object/public/{SUPABASE_IMAGE_BUCKET}/{clean_key}"
                        clean_resp = requests.head(clean_url, timeout=5)
                        if clean_resp.status_code == 200:
                            print(f"[image] ✓ Clean URL works: {clean_url}")
                            return clean_url
                    print(f"[image] Will re-upload with new key")
            except Exception as verify_err:
                print(f"[image] ✗ Could not verify existing URL ({verify_err}), will re-upload")

    # Download image with retry
    content = None
    content_type = "image/jpeg"
    for attempt in range(2):
        try:
            resp = requests.get(image_url, timeout=15, headers=HEADERS, stream=True, allow_redirects=True)
            resp.raise_for_status()
            content = resp.content
            content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
            if len(content) < 100:  # Too small, might be error page
                print(f"[image] Downloaded content too small ({len(content)} bytes), retrying...")
                if attempt == 0:
                    continue
            break
        except Exception as exc:
            print(f"[image] download failed (attempt {attempt+1}/2) for {image_url}: {exc}")
            if attempt == 1:
                return None
            import time
            time.sleep(1)
    
    if not content:
        print(f"[image] Failed to download image content")
        return None

    extension = mimetypes.guess_extension(content_type) or ".jpg"
    # Ensure clean key with no subdirectories
    key_with_ext = f"{file_hash}{extension}"

    try:
        # Supabase SDK expects bytes, not BytesIO - convert directly
        # Combine metadata and file_options into a single file_options dict
        file_options = {
            "content-type": content_type,
            "cache-control": "public, max-age=31536000",
            "upsert": "true"
        }
        # Try to upload, but if file exists, that's okay - we'll use existing
        try:
            print(f"[image] Attempting upload to bucket '{SUPABASE_IMAGE_BUCKET}' with key '{key_with_ext}'...")
            # Supabase storage upload: upload(path, file_bytes, file_options={...})
            # Pass content (bytes) directly, not BytesIO
            image_storage.upload(key_with_ext, content, file_options=file_options)
            print(f"[image] ✓✓✓ Uploaded new thumbnail: {key_with_ext} ({len(content)} bytes)")
        except Exception as upload_exc:
            # File might already exist - that's fine, we'll use the existing one
            error_str = str(upload_exc).lower()
            if any(term in error_str for term in ["already exists", "duplicate", "409", "conflict"]):
                print(f"[image] Thumbnail already exists: {key_with_ext}, using existing")
            elif "bucket" in error_str or "not found" in error_str:
                print(f"[image] ✗✗✗ CRITICAL: Bucket error - {upload_exc}")
                print(f"[image] ✗✗✗ Make sure bucket '{SUPABASE_IMAGE_BUCKET}' exists and is PUBLIC in Supabase dashboard!")
                raise upload_exc
            elif "permission" in error_str or "unauthorized" in error_str or "403" in error_str:
                print(f"[image] ✗✗✗ CRITICAL: Permission error - {upload_exc}")
                print(f"[image] ✗✗✗ Check Supabase storage policies and make bucket PUBLIC!")
                raise upload_exc
            else:
                print(f"[image] Upload error (non-duplicate): {upload_exc}")
                # Try once more with different approach - without upsert
                try:
                    file_options_no_upsert = {
                        "content-type": content_type,
                        "cache-control": "public, max-age=31536000"
                    }
                    image_storage.upload(key_with_ext, content, file_options=file_options_no_upsert)
                    print(f"[image] ✓ Uploaded without upsert: {key_with_ext}")
                except Exception as retry_exc:
                    print(f"[image] ✗ Upload retry also failed: {retry_exc}")
                    import traceback
                    traceback.print_exc()
                    raise upload_exc
    except Exception as exc:
        print(f"[supabase:image] ✗✗✗ UPLOAD FAILED for {image_url}: {exc}")
        import traceback
        traceback.print_exc()
        return None  # Return None on upload failure

    # Always try to get public URL (works for both new uploads and existing files)
    # Wait a moment for Supabase to process the upload
    import time
    time.sleep(0.5)
    
    try:
        public_url = _get_public_url(image_storage, key_with_ext)
        if public_url:
            # Verify the URL actually works before returning it
            for verify_attempt in range(2):
                try:
                    verify_resp = requests.head(public_url, timeout=8, allow_redirects=True)
                    if verify_resp.status_code == 200:
                        print(f"[image] ✓ Public URL verified and working: {public_url[:80]}")
                        return public_url
                    elif verify_resp.status_code == 404 and verify_attempt == 0:
                        # Might need a moment for Supabase to make it public
                        print(f"[image] URL returned 404, waiting 1s and retrying...")
                        time.sleep(1)
                        continue
                    else:
                        print(f"[image] ✗ Public URL returned {verify_resp.status_code}")
                        break
                except Exception as verify_exc:
                    if verify_attempt == 0:
                        print(f"[image] Verification error, retrying: {verify_exc}")
                        time.sleep(1)
                        continue
                    else:
                        print(f"[image] Could not verify URL after retry: {verify_exc}")
                        # Return URL anyway, let frontend handle it
                        return public_url
            
            # If verification failed, try manual construction as last resort
            supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
            if supabase_url:
                from urllib.parse import quote
                clean_key = key_with_ext.lstrip("/").split("/")[-1]
                encoded_key = quote(clean_key, safe='')
                manual_url = f"{supabase_url}/storage/v1/object/public/{SUPABASE_IMAGE_BUCKET}/{encoded_key}"
                print(f"[image] Trying final manual URL: {manual_url[:80]}")
                try:
                    manual_resp = requests.head(manual_url, timeout=8, allow_redirects=True)
                    if manual_resp.status_code == 200:
                        print(f"[image] ✓ Manual URL works: {manual_url[:80]}")
                        return manual_url
                except:
                    pass
            
            # Return the URL anyway - might work on frontend even if HEAD fails
            print(f"[image] Returning URL despite verification issues: {public_url[:80]}")
            return public_url
        else:
            print(f"[image] WARNING: Failed to get public URL for {key_with_ext}")
            return None
    except Exception as exc:
        print(f"[supabase:image] public url failed: {exc}")
        import traceback
        traceback.print_exc()
        return None


def _extract_iocs(text: str, batch_id: str) -> List[Dict[str, str]]:
    matches: List[Dict[str, str]] = []
    ips = set(ipv4.findall(text))
    domains_set = set(domain.findall(text))
    cves = {c.upper() for c in cve.findall(text)}

    matches.extend({"file": batch_id, "type": "ip", "value": ip} for ip in ips)
    matches.extend({"file": batch_id, "type": "domain", "value": dm} for dm in domains_set)
    matches.extend({"file": batch_id, "type": "cve", "value": cv} for cv in cves)
    return matches


def _persist_iocs(iocs: Iterable[Dict[str, str]]) -> None:
    items = list(iocs)
    if not items:
        print("[ioc] no indicators extracted")
        return
    try:
        supabase.table("iocs").insert(items).execute()
        print(f"[ioc] inserted {len(items)} indicators")
    except Exception as exc:
        print(f"[ioc] insertion failed: {exc}")


def fetch_feeds_and_upload(limit_per_feed: int = 12) -> None:
    import sys
    sys.stdout.flush()  # Force immediate output
    print("[ingest] ========================================")
    print("[ingest] fetch_feeds_and_upload() STARTED")
    print(f"[ingest] limit_per_feed: {limit_per_feed}")
    print("[ingest] ========================================")
    sys.stdout.flush()
    import sys
    sys.stdout.flush()  # Force flush to ensure logs appear immediately
    
    print("=" * 60)
    print("[ingest] ============================================")
    
    # Verify bucket exists and is accessible
    try:
        print(f"[ingest] Verifying storage bucket '{SUPABASE_IMAGE_BUCKET}'...")
        buckets = supabase.storage.list_buckets()
        bucket_names = [b.name for b in buckets]
        if SUPABASE_IMAGE_BUCKET not in bucket_names:
            print(f"[ingest] ❌❌❌ CRITICAL ERROR: Bucket '{SUPABASE_IMAGE_BUCKET}' NOT FOUND!")
            print(f"[ingest] Available buckets: {bucket_names}")
            print(f"[ingest]")
            print(f"[ingest] SOLUTION:")
            print(f"[ingest] 1. Go to Supabase Dashboard → Storage")
            print(f"[ingest] 2. Click 'New bucket'")
            print(f"[ingest] 3. Name: {SUPABASE_IMAGE_BUCKET}")
            print(f"[ingest] 4. Toggle 'Public bucket' to ON (CRITICAL!)")
            print(f"[ingest] 5. Click 'Create bucket'")
            print(f"[ingest]")
            print(f"[ingest] Without this bucket, thumbnails will NOT work!")
        else:
            print(f"[ingest] ✓ Bucket '{SUPABASE_IMAGE_BUCKET}' exists")
            # Test if bucket is publicly accessible
            try:
                test_url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{SUPABASE_IMAGE_BUCKET}/test"
                test_resp = requests.head(test_url, timeout=5, allow_redirects=True)
                # 404 is okay (file doesn't exist), but 403 means not public
                if test_resp.status_code == 403:
                    print(f"[ingest] ⚠️  WARNING: Bucket exists but may not be PUBLIC!")
                    print(f"[ingest] Please verify in Supabase Dashboard:")
                    print(f"[ingest]   Storage → {SUPABASE_IMAGE_BUCKET} → Toggle 'Public bucket' ON")
                elif test_resp.status_code in [200, 404]:
                    print(f"[ingest] ✓ Bucket appears to be publicly accessible")
            except Exception as pub_test_err:
                print(f"[ingest] ⚠️  Could not verify public access: {pub_test_err}")
    except Exception as bucket_check_err:
        print(f"[ingest] ❌ Could not verify bucket: {bucket_check_err}")
        import traceback
        traceback.print_exc()
    print("[ingest] STARTING LIVE FEED INGESTION")
    print("[ingest] ============================================")
    print(f"[ingest] Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"[ingest] Image bucket: {SUPABASE_IMAGE_BUCKET}")
    print(f"[ingest] Supabase URL: {SUPABASE_URL[:50]}..." if SUPABASE_URL else "[ingest] Supabase URL: NOT SET")
    print("=" * 60)
    sys.stdout.flush()
    
    collected: List[Dict[str, str]] = []
    print("[ingest] fetching live feeds…")
    sys.stdout.flush()

    for feed_url, meta in FEEDS.items():
        try:
            parsed = feedparser.parse(feed_url)
        except Exception as exc:
            print(f"[feed] failed to parse {feed_url}: {exc}")
            continue

        source_label = meta.get("name") or _resolve_source_name(feed_url, "Unknown Source")

        for entry in parsed.entries[:limit_per_feed]:
            link = entry.get("link") or ""
            if not link:
                continue

            title = _clean_text(entry.get("title"))
            cleaned_summary = _clean_text(entry.get("summary") or entry.get("description"))
            
            # Filter out non-cybersecurity articles
            if not _is_cybersecurity_article(title, cleaned_summary):
                print(f"[filter] Skipping non-cybersecurity article: {title[:60]}...")
                continue

            article = {
                "title": title,
                "description": cleaned_summary,
                "link": link,
                "source": feed_url,
                "source_name": source_label,
                "published_at": _parse_datetime(entry),
                "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
            }

            # Extract and upload thumbnail - ALWAYS try to get an image
            uploaded_url = None
            print(f"[article] Processing thumbnail for: {title[:50]}...")
            
            # Method 0: Try RSS feed entry image first (fastest, most reliable)
            try:
                # Check if RSS entry has media:thumbnail or media:content
                media_thumbnail = entry.get("media_thumbnail") or entry.get("media_content")
                if media_thumbnail:
                    if isinstance(media_thumbnail, list) and len(media_thumbnail) > 0:
                        rss_image_url = media_thumbnail[0].get("url") or media_thumbnail[0].get("href")
                    elif isinstance(media_thumbnail, dict):
                        rss_image_url = media_thumbnail.get("url") or media_thumbnail.get("href")
                    else:
                        rss_image_url = str(media_thumbnail) if media_thumbnail else None
                    
                    if rss_image_url and rss_image_url.startswith("http"):
                        print(f"[article] Found RSS feed image: {rss_image_url[:100]}")
                        uploaded_url = _upload_image_to_supabase(rss_image_url)
                        if uploaded_url:
                            print(f"[article] ✓✓✓ Uploaded RSS feed image: {uploaded_url[:100]}")
                
                # Also check for links with rel="enclosure" (common in RSS)
                if not uploaded_url:
                    links = entry.get("links", [])
                    for link_obj in links:
                        if isinstance(link_obj, dict) and link_obj.get("rel") == "enclosure":
                            enclosure_url = link_obj.get("href")
                            if enclosure_url and any(ext in enclosure_url.lower() for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]):
                                print(f"[article] Found RSS enclosure image: {enclosure_url[:100]}")
                                uploaded_url = _upload_image_to_supabase(enclosure_url)
                                if uploaded_url:
                                    print(f"[article] ✓✓✓ Uploaded RSS enclosure image: {uploaded_url[:100]}")
                                    break
            except Exception as rss_err:
                print(f"[article] RSS image extraction error: {rss_err}")
            
            # Method 1: Try OG image extraction
            if not uploaded_url:
                try:
                    og_image = _extract_image_url(link)
                    if og_image:
                        print(f"[article] Extracted OG image: {og_image[:100]}")
                        uploaded_url = _upload_image_to_supabase(og_image)
                        if uploaded_url:
                            print(f"[article] ✓✓✓ Uploaded OG image: {uploaded_url[:100]}")
                        else:
                            print(f"[article] ✗ OG image upload failed, trying screenshot...")
                    else:
                        print(f"[article] ✗ No OG image found, trying screenshot...")
                except Exception as og_err:
                    print(f"[article] ✗ OG extraction error: {og_err}, trying screenshot...")
            
            # Method 2: If OG image failed, try screenshot service as fallback
            if not uploaded_url:
                try:
                    print(f"[article] Attempting screenshot service for {link[:60]}")
                    screenshot_url = _get_screenshot_url(link)
                    if screenshot_url:
                        print(f"[article] Got screenshot URL: {screenshot_url[:100]}")
                        uploaded_url = _upload_image_to_supabase(screenshot_url)
                        if uploaded_url:
                            print(f"[article] ✓✓✓ Uploaded screenshot: {uploaded_url[:100]}")
                        else:
                            print(f"[article] ✗ Screenshot upload failed")
                    else:
                        print(f"[article] ✗ Screenshot service returned no URL")
                except Exception as screenshot_err:
                    print(f"[article] ✗ Screenshot service error: {screenshot_err}")
            
            if uploaded_url:
                # CRITICAL: Verify the URL works before saving
                final_url = uploaded_url
                try:
                    test_resp = requests.head(uploaded_url, timeout=10, allow_redirects=True)
                    if test_resp.status_code == 200:
                        print(f"[article] ✓✓✓ VERIFIED thumbnail URL works: {uploaded_url[:100]}")
                        final_url = uploaded_url
                    else:
                        print(f"[article] ⚠️  Thumbnail URL returned {test_resp.status_code}: {uploaded_url[:100]}")
                        # Try to fix the URL
                        if "supabase.co" in uploaded_url:
                            # Extract just the filename from the URL
                            from urllib.parse import urlparse, unquote
                            parsed = urlparse(uploaded_url)
                            path_parts = parsed.path.split("/")
                            filename = path_parts[-1] if path_parts else None
                            if filename:
                                # Reconstruct with correct bucket
                                fixed_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_IMAGE_BUCKET}/{filename}"
                                print(f"[article] Trying fixed URL: {fixed_url[:100]}")
                                try:
                                    fixed_resp = requests.head(fixed_url, timeout=10, allow_redirects=True)
                                    if fixed_resp.status_code == 200:
                                        print(f"[article] ✓✓✓ Fixed URL works: {fixed_url[:100]}")
                                        final_url = fixed_url
                                    else:
                                        print(f"[article] ⚠️  Fixed URL returned {fixed_resp.status_code}, but saving anyway")
                                        # Save the fixed URL anyway - might work on frontend
                                        final_url = fixed_url
                                except:
                                    print(f"[article] ⚠️  Could not test fixed URL, but saving anyway")
                                    final_url = fixed_url
                        # Even if verification failed, save the URL - might work on frontend
                        # Don't set to None - let frontend handle it
                except Exception as verify_final:
                    print(f"[article] ⚠️  Could not verify URL: {verify_final}, but saving anyway")
                    # Save anyway - might work on frontend or after Supabase processes it
                    final_url = uploaded_url
                
                # Always save the URL if we have one (even if verification failed)
                article["image_url"] = final_url
                print(f"[article] ✓✓✓ FINAL: Saved image_url: {final_url[:100]}")
            else:
                print(f"[article] ✗✗✗ FAILED: No thumbnail for: {title[:50]}...")
                print(f"[article]   Link: {link[:80]}")
                # Don't set to None - use empty string or omit the field
                article["image_url"] = ""  # Empty string instead of None
            
            collected.append(article)

    if not collected:
        print("[ingest] no articles collected. aborting.")
        return

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    batch_id = f"live_feed_{timestamp}.json"

    # Upload raw batch to storage
    try:
        raw_bytes = json.dumps(collected, indent=2, ensure_ascii=False).encode("utf-8")
        storage.upload(f"raw-feeds/{batch_id}", io.BytesIO(raw_bytes), {"content-type": "application/json"})
        print(f"[storage] raw batch uploaded -> raw-feeds/{batch_id}")
    except Exception as exc:
        print(f"[storage] failed to upload raw batch: {exc}")

    # Upsert articles into Supabase table (unique per link)
    try:
        # Log image URLs before upsert
        # Clean up None values - convert to empty string
        for art in collected:
            if art.get("image_url") is None:
                art["image_url"] = ""
        
        articles_with_images = sum(1 for a in collected if a.get("image_url") and a.get("image_url").strip())
        print(f"[articles] About to upsert {len(collected)} articles, {articles_with_images} have image_url")
        for i, art in enumerate(collected[:5]):  # Log first 5
            img = art.get("image_url") or ""
            print(f"[articles] Article {i+1}: '{art.get('title', '')[:40]}' -> image_url: {img[:100] if img else 'NONE/EMPTY'}")
        
        response = supabase.table("articles").upsert(
            collected,
            on_conflict="link",
        ).execute()
        inserted = len(response.data) if getattr(response, "data", None) else len(collected)
        print(f"[articles] ✓ upserted {inserted} records")
        
        # Verify what was actually saved
        if response.data:
            for i, saved in enumerate(response.data[:3]):
                saved_img = saved.get("image_url")
                print(f"[articles] Saved article {i+1}: image_url = {saved_img[:100] if saved_img else 'NONE'}")
    except Exception as exc:
        print(f"[articles] ✗ upsert failed: {exc}")
        import traceback
        traceback.print_exc()

    # Extract IOCs for this batch
    all_text = [
        " ".join(filter(None, [item.get("title"), item.get("description"), item.get("link")]))
        for item in collected
    ]
    indicators = []
    for text in all_text:
        indicators.extend(_extract_iocs(text, batch_id))
    _persist_iocs(indicators)


if __name__ == "__main__":
    import sys
    sys.stdout.flush()  # Force immediate output
    try:
        print("[SCRIPT] ========================================")
        print("[SCRIPT] live_ingest_supabase.py STARTED")
        print("[SCRIPT] ========================================")
        sys.stdout.flush()
        
        print("[SCRIPT] Environment check:")
        print(f"[SCRIPT]   SUPABASE_URL: {'SET' if SUPABASE_URL else 'MISSING'}")
        print(f"[SCRIPT]   SUPABASE_KEY: {'SET' if SUPABASE_KEY else 'MISSING'}")
        print(f"[SCRIPT]   SUPABASE_IMAGE_BUCKET: {SUPABASE_IMAGE_BUCKET}")
        sys.stdout.flush()
        
        print("[SCRIPT] Starting fetch_feeds_and_upload()...")
        sys.stdout.flush()
        
        fetch_feeds_and_upload()
        
        print("[SCRIPT] ========================================")
        print("[SCRIPT] live_ingest_supabase.py COMPLETED SUCCESSFULLY")
        print("[SCRIPT] ========================================")
        sys.stdout.flush()
    except Exception as e:
        print(f"[SCRIPT] ========================================")
        print(f"[SCRIPT] ERROR: {e}")
        print("[SCRIPT] ========================================")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        raise

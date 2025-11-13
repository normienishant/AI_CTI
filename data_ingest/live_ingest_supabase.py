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
        # Method 1: Try the get_public_url method
        try:
            result = client.get_public_url(key)
            if isinstance(result, dict):
                url = result.get("publicUrl") or result.get("publicURL") or result.get("public_url")
                if url and url.startswith("http"):
                    print(f"[image] Got public URL from API: {url[:80]}")
                    return url
            if isinstance(result, str) and result.startswith("http"):
                print(f"[image] Got public URL from API (string): {result[:80]}")
                return result
        except Exception as api_exc:
            print(f"[image] get_public_url API method failed: {api_exc}")
        
        # Method 2: Construct URL manually (fallback)
        # Format: https://{project_ref}.supabase.co/storage/v1/object/public/{bucket}/{key}
        supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        if supabase_url and SUPABASE_IMAGE_BUCKET:
            try:
                from urllib.parse import urlparse, quote
                parsed = urlparse(supabase_url)
                # URL encode the key in case it has special characters
                encoded_key = quote(key, safe='/')
                public_url = f"{supabase_url}/storage/v1/object/public/{SUPABASE_IMAGE_BUCKET}/{encoded_key}"
                print(f"[image] Constructed public URL: {public_url[:80]}")
                return public_url
            except Exception as const_exc:
                print(f"[image] URL construction failed: {const_exc}")
        
        print(f"[image] ✗ Could not generate public URL for {key}")
        return None
    except Exception as exc:
        print(f"[image] get_public_url failed for {key}: {exc}")
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

    try:
        resp = requests.get(image_url, timeout=12, headers=HEADERS, stream=True)
        resp.raise_for_status()
        content = resp.content
    except Exception as exc:
        print(f"[image] download failed for {image_url}: {exc}")
        return None

    content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
    extension = mimetypes.guess_extension(content_type) or ".jpg"
    key_with_ext = f"{file_hash}{extension}"

    try:
        buffer = io.BytesIO(content)
        metadata = {"content-type": content_type}
        # Try to upload, but if file exists, that's okay - we'll use existing
        try:
            image_storage.upload(key_with_ext, buffer, metadata)
            print(f"[image] Uploaded new thumbnail: {key_with_ext}")
        except Exception as upload_exc:
            # File might already exist - that's fine, we'll use the existing one
            if "already exists" in str(upload_exc).lower() or "duplicate" in str(upload_exc).lower():
                print(f"[image] Thumbnail already exists: {key_with_ext}, using existing")
            else:
                raise upload_exc
    except Exception as exc:
        print(f"[supabase:image] upload failed for {image_url}: {exc}")

    # Always try to get public URL (works for both new uploads and existing files)
    try:
        public_url = _get_public_url(image_storage, key_with_ext)
        if public_url:
            # Verify the URL actually works before returning it
            try:
                verify_resp = requests.head(public_url, timeout=5, allow_redirects=True)
                if verify_resp.status_code == 200:
                    print(f"[image] ✓ Public URL verified and working: {public_url[:80]}")
                    return public_url
                else:
                    print(f"[image] ✗ Public URL returned {verify_resp.status_code}, trying manual construction")
                    # Try to construct URL manually without any subdirectories
                    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
                    if supabase_url:
                        # Remove any subdirectory from key (like "6/")
                        clean_key = key_with_ext.lstrip("/").split("/")[-1]  # Get just filename
                        manual_url = f"{supabase_url}/storage/v1/object/public/{SUPABASE_IMAGE_BUCKET}/{clean_key}"
                        print(f"[image] Trying clean manual URL: {manual_url[:80]}")
                        manual_resp = requests.head(manual_url, timeout=5)
                        if manual_resp.status_code == 200:
                            print(f"[image] ✓ Clean URL works: {manual_url[:80]}")
                            return manual_url
                    print(f"[image] ✗ All URL attempts failed for {key_with_ext}")
                    return None
            except Exception as verify_exc:
                print(f"[image] Could not verify URL: {verify_exc}, returning anyway")
                # Return URL anyway, let frontend handle it
                return public_url
        else:
            print(f"[image] WARNING: Failed to get public URL for {key_with_ext}")
            return None
    except Exception as exc:
        print(f"[supabase:image] public url failed: {exc}")
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
    sys.stdout.flush()  # Force flush to ensure logs appear immediately
    
    print("=" * 60)
    print("[ingest] ============================================")
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

            # Extract and upload thumbnail
            og_image = _extract_image_url(link)
            uploaded_url = None
            if og_image:
                print(f"[article] Extracted OG image: {og_image[:100]}")
                uploaded_url = _upload_image_to_supabase(og_image)
                if uploaded_url:
                    print(f"[article] ✓ Using Supabase thumbnail: {uploaded_url[:100]}")
                else:
                    print(f"[article] ✗ Failed to upload thumbnail, using OG image: {og_image[:100]}")
            else:
                print(f"[article] ✗ No OG image found for: {title[:50]}...")
            
            # Prioritize Supabase URL, then OG image, then default
            article["image_url"] = uploaded_url or og_image or DEFAULT_IMAGE_URL
            if not article["image_url"] or article["image_url"] == DEFAULT_IMAGE_URL:
                print(f"[article] ⚠ No thumbnail for: {title[:50]}... (using default)")
            else:
                print(f"[article] ✓ Final image_url set: {article['image_url'][:100]}")
            
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
        response = supabase.table("articles").upsert(
            collected,
            on_conflict="link",
        ).execute()
        inserted = len(response.data) if getattr(response, "data", None) else len(collected)
        print(f"[articles] upserted {inserted} records")
    except Exception as exc:
        print(f"[articles] upsert failed: {exc}")

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
    try:
        print("[SCRIPT] live_ingest_supabase.py started")
        print("[SCRIPT] Environment check:")
        print(f"[SCRIPT]   SUPABASE_URL: {'SET' if SUPABASE_URL else 'MISSING'}")
        print(f"[SCRIPT]   SUPABASE_KEY: {'SET' if SUPABASE_KEY else 'MISSING'}")
        print(f"[SCRIPT]   SUPABASE_IMAGE_BUCKET: {SUPABASE_IMAGE_BUCKET}")
        fetch_feeds_and_upload()
        print("[SCRIPT] live_ingest_supabase.py completed successfully")
    except Exception as e:
        print(f"[SCRIPT] ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise

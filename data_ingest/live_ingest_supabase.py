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

# Rotate user agents to avoid IP bans
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
]

import random
HEADERS = {
    "User-Agent": random.choice(USER_AGENTS),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
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
    """Get screenshot URL using screenshot API service as fallback - IMPROVED with retries"""
    if not article_url:
        return None
    
    print(f"[screenshot] ========================================")
    print(f"[screenshot] Attempting screenshot for: {article_url[:80]}")
    print(f"[screenshot] ========================================")
    
    # Method 1: Try microlink.io screenshot API (free, no API key required) - MOST RELIABLE
    for attempt in range(2):  # Retry once
        try:
            microlink_url = f"https://api.microlink.io/?url={requests.utils.quote(article_url)}&screenshot=true&viewport.width=1200&viewport.height=630&waitUntil=networkidle0"
            print(f"[screenshot] [Attempt {attempt+1}/2] Trying microlink.io...")
            resp = requests.get(microlink_url, timeout=20, headers=HEADERS, allow_redirects=True)
            print(f"[screenshot] microlink.io response: {resp.status_code}")
            
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    screenshot_url = data.get("data", {}).get("screenshot", {}).get("url")
                    if screenshot_url and screenshot_url.startswith("http"):
                        print(f"[screenshot] ✓✓✓ Got screenshot URL from microlink: {screenshot_url[:100]}")
                        # Verify the screenshot URL works
                        try:
                            verify_resp = requests.head(screenshot_url, timeout=10, allow_redirects=True)
                            if verify_resp.status_code == 200:
                                print(f"[screenshot] ✓✓✓ Screenshot URL verified and working!")
                                return screenshot_url
                            else:
                                print(f"[screenshot] ⚠️  Screenshot URL returned {verify_resp.status_code}, but returning anyway")
                                return screenshot_url  # Return anyway - might work
                        except Exception as verify_err:
                            print(f"[screenshot] ⚠️  Could not verify screenshot URL: {verify_err}, but returning anyway")
                            return screenshot_url  # Return anyway - might work
                    else:
                        print(f"[screenshot] ✗ No screenshot URL in microlink response")
                except Exception as parse_err:
                    print(f"[screenshot] ✗ Failed to parse microlink response: {parse_err}")
            elif resp.status_code == 429:
                print(f"[screenshot] ⚠️  Rate limited, waiting 2s before retry...")
                import time
                time.sleep(2)
                continue
            else:
                print(f"[screenshot] ✗ microlink.io returned {resp.status_code}")
        except requests.exceptions.Timeout:
            print(f"[screenshot] ✗ microlink.io timeout (attempt {attempt+1})")
            if attempt == 0:
                import time
                time.sleep(1)
                continue
        except Exception as exc:
            print(f"[screenshot] ✗ microlink.io error: {exc}")
            if attempt == 0:
                import time
                time.sleep(1)
                continue
    
    # Method 2: Try screenshotapi.net (free tier)
    try:
        screenshot_api_key = os.getenv("SCREENSHOT_API_KEY", "free")
        screenshot_api2 = f"https://shot.screenshotapi.net/screenshot?token={screenshot_api_key}&url={requests.utils.quote(article_url)}&width=1200&height=630&output=image&file_type=png&wait_for_event=load"
        print(f"[screenshot] Trying screenshotapi.net...")
        resp2 = requests.get(screenshot_api2, timeout=20, allow_redirects=True)
        print(f"[screenshot] screenshotapi.net response: {resp2.status_code}")
        
        if resp2.status_code == 200:
            # screenshotapi.net returns the image directly or a redirect
            final_url = resp2.url if resp2.url != screenshot_api2 else screenshot_api2
            # Check if it's actually an image
            content_type = resp2.headers.get("content-type", "")
            if "image" in content_type or final_url.endswith((".png", ".jpg", ".jpeg")):
                print(f"[screenshot] ✓✓✓ Got screenshot from screenshotapi.net: {final_url[:100]}")
                return final_url
            else:
                print(f"[screenshot] ✗ screenshotapi.net returned non-image content")
    except Exception as exc:
        print(f"[screenshot] ✗ screenshotapi.net failed: {exc}")
    
    # Method 3: Try htmlcsstoimage.com (requires API key)
    try:
        htmlcsstoimage_api_key = os.getenv("HTMLCSSTOIMAGE_API_KEY")
        if htmlcsstoimage_api_key:
            htmlcss_url = f"https://hcti.io/v1/image?url={requests.utils.quote(article_url)}"
            print(f"[screenshot] Trying htmlcsstoimage.com...")
            resp3 = requests.post(htmlcss_url, auth=(htmlcsstoimage_api_key, ''), timeout=20)
            if resp3.status_code == 200:
                data3 = resp3.json()
                screenshot_url3 = data3.get("url")
                if screenshot_url3:
                    print(f"[screenshot] ✓✓✓ Got screenshot from htmlcsstoimage: {screenshot_url3[:80]}")
                    return screenshot_url3
        else:
            print(f"[screenshot] ⚠️  htmlcsstoimage API key not set, skipping")
    except Exception as exc:
        print(f"[screenshot] ✗ htmlcsstoimage failed: {exc}")
    
    print(f"[screenshot] ✗✗✗ All screenshot services failed for {article_url[:60]}")
    return None


def _validate_image_url(image_url: str, article_url: str = None) -> bool:
    """Validate that an image URL actually returns a valid image (not error page, not white page, not screenshot service)"""
    if not image_url or not image_url.startswith("http"):
        return False
    
    url_lower = image_url.lower()
    
    # Skip screenshot service URLs
    if any(blocked in url_lower for blocked in ["screenshot", "microlink", "shot", "htmlcsstoimage", "api.screenshot"]):
        print(f"[image]   ✗ Rejecting screenshot service URL: {image_url[:80]}")
        return False
    
    # Site-specific filtering for SecurityWeek and DarkReading
    # These sites often provide banner/header OG images instead of article images
    if article_url:
        article_url_lower = article_url.lower()
        if "securityweek.com" in article_url_lower:
            # SecurityWeek OG images are often banners - skip common banner patterns
            if any(banner_pattern in url_lower for banner_pattern in [
                "og-image", "default", "logo", "banner", "header", 
                "securityweek.com/images", "securityweek.com/assets"
            ]):
                print(f"[image]   ✗ Rejecting SecurityWeek banner/header OG image: {image_url[:80]}")
                return False
        
        if "darkreading.com" in article_url_lower:
            # DarkReading OG images are often banners - skip common banner patterns
            if any(banner_pattern in url_lower for banner_pattern in [
                "og-image", "default", "logo", "banner", "header",
                "darkreading.com/images", "darkreading.com/assets", "social-share"
            ]):
                print(f"[image]   ✗ Rejecting DarkReading banner/header OG image: {image_url[:80]}")
                return False
    
    # Try to validate the image by checking headers
    try:
        # Use HEAD request first (faster)
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        resp = requests.head(image_url, timeout=8, headers=headers, allow_redirects=True)
        
        # Check for Cloudflare errors
        if resp.status_code == 403 or resp.status_code == 429:
            print(f"[image]   ✗ Image URL blocked (Cloudflare?): {resp.status_code}")
            return False
        
        # Check content type
        content_type = resp.headers.get("Content-Type", "").lower()
        if not any(img_type in content_type for img_type in ["image/", "jpeg", "png", "webp", "gif"]):
            # If HEAD doesn't give content-type, try GET with limited data
            if "text/html" in content_type or "application/json" in content_type:
                print(f"[image]   ✗ URL returns HTML/JSON, not image: {content_type}")
                return False
        
        # Check content length (too small might be error page)
        content_length = resp.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) < 500:  # Less than 500 bytes is suspicious
                    print(f"[image]   ✗ Image too small ({content_length} bytes), likely error page")
                    return False
            except:
                pass
        
        # If HEAD worked, do a small GET to verify it's actually an image
        if resp.status_code == 200:
            get_resp = requests.get(image_url, timeout=8, headers=headers, stream=True, allow_redirects=True)
            # Read only first 1KB to check
            chunk = next(get_resp.iter_content(1024), b"")
            if len(chunk) < 100:
                print(f"[image]   ✗ Image content too small, likely error page")
                return False
            
            # Check if it's HTML (error page)
            chunk_str = chunk[:200].decode("utf-8", errors="ignore").lower()
            if any(error_indicator in chunk_str for error_indicator in [
                "<html", "<!doctype", "error", "cloudflare", "access denied", 
                "403", "404", "500", "blocked", "banned"
            ]):
                print(f"[image]   ✗ URL returns HTML error page, not image")
                return False
            
            # Check image magic bytes
            if chunk.startswith(b"\xff\xd8\xff") or chunk.startswith(b"\x89PNG") or \
               chunk.startswith(b"GIF8") or chunk.startswith(b"RIFF") or \
               chunk.startswith(b"\x00\x00\x01\x00") or chunk.startswith(b"WEBP"):
                # Try to get image dimensions to check if it's a banner/header
                # Banners are usually very wide and short (e.g., 1200x200)
                # Article images are usually more square or portrait (e.g., 800x600, 1200x800)
                try:
                    from PIL import Image
                    import io
                    # Read more data to get full image
                    full_content = b""
                    for chunk_data in get_resp.iter_content(8192):
                        full_content += chunk_data
                        if len(full_content) > 50000:  # Read up to 50KB for dimension check
                            break
                    
                    img = Image.open(io.BytesIO(full_content))
                    width, height = img.size
                    aspect_ratio = width / height if height > 0 else 0
                    
                    # Skip if it's a banner (very wide and short)
                    # Typical banners: width > 1000 and aspect_ratio > 4:1 (width/height > 4)
                    # Also check for very wide images (aspect ratio > 3.5:1) as they're likely banners
                    if width > 1000 and aspect_ratio > 3.5:
                        print(f"[image]   ✗ Image appears to be a banner/header ({width}x{height}, ratio: {aspect_ratio:.2f})")
                        return False
                    
                    # For SecurityWeek/DarkReading, be even more strict - reject anything wider than 3:1
                    if article_url and any(site in article_url.lower() for site in ["securityweek.com", "darkreading.com"]):
                        if aspect_ratio > 3.0:
                            print(f"[image]   ✗ Image too wide for article image ({width}x{height}, ratio: {aspect_ratio:.2f}) - likely banner")
                            return False
                    
                    # Skip if it's too small (likely icon/logo)
                    if width < 300 or height < 200:
                        print(f"[image]   ✗ Image too small ({width}x{height}), likely icon/logo")
                        return False
                    
                    print(f"[image]   ✓ Valid article image detected ({width}x{height}, ratio: {aspect_ratio:.2f})")
                    return True
                except ImportError:
                    # PIL not available, skip dimension check
                    print(f"[image]   ✓ Valid image detected (magic bytes, PIL not available for dimension check)")
                    return True
                except Exception as dim_err:
                    # Dimension check failed, but image is valid
                    print(f"[image]   ✓ Valid image detected (magic bytes, dimension check failed: {dim_err})")
                    return True
            else:
                print(f"[image]   ✗ No image magic bytes found")
                return False
        
        return resp.status_code == 200
        
    except requests.exceptions.RequestException as e:
        print(f"[image]   ✗ Could not validate image URL: {e}")
        return False
    except Exception as e:
        print(f"[image]   ✗ Validation error: {e}")
        return False


def _extract_image_url(article_url: str) -> Optional[str]:
    """Extract featured/OG image from article - ENHANCED to find actual article images, not full page screenshots"""
    print(f"[image] ========================================")
    print(f"[image] EXTRACTING FEATURED IMAGE FROM: {article_url[:80]}")
    print(f"[image] ========================================")
    
    # Rotate user agent for this request
    headers = HEADERS.copy()
    headers["User-Agent"] = random.choice(USER_AGENTS)
    
    try:
        resp = requests.get(article_url, timeout=20, headers=headers, allow_redirects=True)
        
        # Check for Cloudflare blocks
        if resp.status_code == 403:
            print(f"[image] ✗✗✗ Cloudflare blocked (403) - IP might be banned")
            return None
        if resp.status_code == 429:
            print(f"[image] ✗✗✗ Rate limited (429) - too many requests")
            return None
        
        resp.raise_for_status()
        print(f"[image] ✓ Successfully fetched article HTML ({len(resp.text)} bytes)")
    except requests.exceptions.HTTPError as e:
        if e.response and e.response.status_code in [403, 429]:
            print(f"[image] ✗✗✗ HTTP error {e.response.status_code} - likely blocked")
        else:
            print(f"[image] ✗✗✗ HTTP error: {e}")
        return None
    except Exception as exc:
        print(f"[image] ✗✗✗ Fetch failed for {article_url}: {exc}")
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    
    # Special handling for SecurityWeek and DarkReading
    # These sites often provide banner/header OG images, so we skip OG and look for actual article images
    article_url_lower = article_url.lower()
    skip_og_for_sites = ["securityweek.com", "darkreading.com"]
    should_skip_og = any(site in article_url_lower for site in skip_og_for_sites)
    
    if should_skip_og:
        print(f"[image] ⚠️  Detected {article_url_lower.split('.')[1] if '.' in article_url_lower else 'site'} - skipping OG images (often banners), will look for actual article images")
    
    # Method 1: Try OG/Twitter meta tags (MOST RELIABLE - these are actual featured images)
    # This is the PRIMARY method - most sites have OG images
    # BUT: Skip for SecurityWeek/DarkReading as they provide banner OG images
    if not should_skip_og:
        print(f"[image] Method 1: Checking OG/Twitter meta tags...")
    meta_selectors = [
        ("meta", {"property": "og:image"}),
        ("meta", {"name": "og:image"}),
        ("meta", {"property": "twitter:image"}),
        ("meta", {"name": "twitter:image"}),
        ("meta", {"property": "og:image:url"}),
        ("meta", {"name": "twitter:image:src"}),
        ("meta", {"property": "twitter:image:src"}),
        ("link", {"rel": "image_src"}),  # Some sites use this
        ("link", {"rel": "preload", "as": "image"}),  # Some sites preload featured images
    ]
    
    found_meta_images = []
    for tag_name, attrs in meta_selectors:
        tags = soup.find_all(tag_name, attrs=attrs) if tag_name == "link" else [soup.find(tag_name, attrs=attrs)]
        for tag in tags:
            if not tag:
                continue
            url = tag.get("content") or tag.get("href") or tag.get("imagesrcset")
            if url:
                url = url.strip()
                # Handle srcset (take first URL)
                if " " in url:
                    url = url.split()[0]
                # Skip placeholder/default images AND banners/headers/logos
                url_lower = url.lower()
                # Skip placeholder/default images AND banners/headers/logos
                url_lower = url.lower()
                if any(skip in url_lower for skip in [
                    "placeholder", "default", "logo-only", "no-image", "1x1", "blank",
                    "banner", "header", "nav", "navigation", "topbar", "top-bar", 
                    "site-logo", "site-logo", "brand", "logo", "favicon"
                ]):
                    print(f"[image]   ✗ Skipping placeholder/banner/logo: {url[:60]}")
                    continue
                
                if url.startswith("//"):
                    parsed = urlparse(article_url)
                    url = f"{parsed.scheme}:{url}"
                if url.startswith("http") and not url.startswith("http://localhost"):
                    # CRITICAL: Verify it's not a screenshot service URL
                    if "screenshot" not in url_lower and "microlink" not in url_lower and "shot" not in url_lower:
                        found_meta_images.append(url)
                        print(f"[image]   ✓ Found potential OG image: {url[:100]}")
    
    # Validate and return the first valid OG image found
    # For SecurityWeek and DarkReading, be more strict - skip OG images that look like banners
    if not should_skip_og:
        for img_url in found_meta_images:
            if _validate_image_url(img_url, article_url):
                print(f"[image] ✓✓✓✓✓ VALIDATED OG/Twitter meta image: {img_url[:100]}")
                return img_url
            else:
                print(f"[image]   ✗ OG image failed validation, trying next...")
        
        print(f"[image] ✗ No valid OG/Twitter meta images found (all failed validation)")
    else:
        print(f"[image] ⚠️  Skipping OG images for this site (known to provide banners)")
    
    # Method 2: Try to find article featured image in common HTML patterns
    # Look for article featured images, hero images (NOT site headers/banners)
    print(f"[image] Method 2: Checking HTML patterns for featured images...")
    article_selectors = [
        # REMOVED "header" - it matches site headers, not article images
        ("img", {"class": re.compile(r"featured|hero|article-image|post-image|thumbnail|entry-image|wp-post-image|attachment-post-thumbnail|post-thumbnail", re.I)}),
        ("img", {"id": re.compile(r"featured|hero|article-image|post-image|main-image|post-thumbnail|entry-image", re.I)}),
        ("img", {"data-src": re.compile(r"featured|hero|article", re.I)}),
        ("div", {"class": re.compile(r"featured-image|hero-image|article-image|post-thumbnail|entry-thumbnail|post-featured|wp-post-image", re.I)}),
        ("figure", {"class": re.compile(r"featured|article-image|post-image|wp-block-image|wp-caption", re.I)}),
        ("picture", {"class": re.compile(r"featured|hero|article-image", re.I)}),
        # REMOVED "article-header" - might match site headers
        ("section", {"class": re.compile(r"featured-image|hero-image", re.I)}),
    ]
    
    for selector_type, attrs in article_selectors:
        elements = soup.find_all(selector_type, attrs=attrs, limit=5)  # Limit to first 5 matches
        for elem in elements:
            if selector_type == "img":
                img_url = elem.get("src") or elem.get("data-src") or elem.get("data-lazy-src") or elem.get("data-original")
            else:
                # For div/figure/picture, find img inside
                img = elem.find("img")
                if img:
                    img_url = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or img.get("data-original")
                else:
                    continue
            
            if img_url:
                # Skip placeholder/default images AND banners/headers/logos
                img_url_lower = img_url.lower()
                if any(skip in img_url_lower for skip in [
                    "placeholder", "default", "logo-only", "no-image", "1x1", "spacer",
                    "banner", "header", "nav", "navigation", "topbar", "top-bar",
                    "site-logo", "brand", "logo", "favicon", "menu", "navbar"
                ]):
                    print(f"[image]   ✗ Skipping banner/header/logo: {img_url[:60]}")
                    continue
                
                # Check if image is inside a header/nav/banner element (skip those)
                parent = elem.parent if selector_type == "img" else elem
                if parent:
                    parent_classes = " ".join(parent.get("class", [])).lower()
                    parent_id = (parent.get("id") or "").lower()
                    if any(skip in parent_classes or skip in parent_id for skip in [
                        "header", "banner", "nav", "navigation", "topbar", "top-bar",
                        "site-header", "main-header", "page-header", "navbar"
                    ]):
                        print(f"[image]   ✗ Image is inside header/banner element, skipping")
                        continue
                
                # Resolve relative URLs
                if img_url.startswith("//"):
                    parsed = urlparse(article_url)
                    img_url = f"{parsed.scheme}:{img_url}"
                elif img_url.startswith("/"):
                    parsed = urlparse(article_url)
                    img_url = f"{parsed.scheme}://{parsed.netloc}{img_url}"
                elif not img_url.startswith("http"):
                    continue
                
                # Skip screenshot service URLs
                if "screenshot" in img_url_lower or "microlink" in img_url_lower:
                    continue
                
                # Verify it's a real image URL (not a placeholder or icon)
                # Skip screenshot service URLs
                if "screenshot" in img_url_lower or "microlink" in img_url_lower or "shot" in img_url_lower:
                    print(f"[image]   ✗ Skipping screenshot service URL: {img_url[:60]}")
                    continue
                
                if any(ext in img_url_lower for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]) or "image" in img_url_lower:
                    if _validate_image_url(img_url, article_url):
                        print(f"[image] ✓✓✓✓✓ VALIDATED article featured image (HTML pattern): {img_url[:100]}")
                        return img_url
                    else:
                        print(f"[image]   ✗ HTML pattern image failed validation, trying next...")
                        continue
    
    # Method 3: Find first large image in article content (not icons/logos)
    print(f"[image] Method 3: Checking article content for large images...")
    article_content = soup.find("article") or soup.find("main") or soup.find("div", {"class": re.compile(r"content|post|article|entry-content", re.I)})
    if article_content:
        images = article_content.find_all("img", limit=10)  # Limit to first 10 images
        for img in images:
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or img.get("data-original")
            if not src:
                continue
            
            src_lower = src.lower()
            
            # Skip placeholder/default images AND banners/headers/logos
            if any(skip in src_lower for skip in [
                "placeholder", "default", "logo-only", "no-image", "1x1", "spacer", "blank",
                "banner", "header", "nav", "navigation", "topbar", "top-bar",
                "site-logo", "brand", "logo", "favicon", "menu", "navbar"
            ]):
                continue
            
            # Check if image is inside a header/nav/banner element (skip those)
            parent = img.parent
            while parent and parent.name not in ["article", "main", "body"]:
                parent_classes = " ".join(parent.get("class", [])).lower()
                parent_id = (parent.get("id") or "").lower()
                if any(skip in parent_classes or skip in parent_id for skip in [
                    "header", "banner", "nav", "navigation", "topbar", "top-bar",
                    "site-header", "main-header", "page-header", "navbar", "menu"
                ]):
                    print(f"[image]   ✗ Image is inside header/banner element, skipping")
                    break
                parent = parent.parent
            else:
                # If we broke out of the loop, skip this image
                if parent and parent.name not in ["article", "main", "body"]:
                    continue
            
            # Skip small images (likely icons/logos)
            width = img.get("width")
            height = img.get("height")
            if width and height:
                try:
                    w, h = int(width), int(height)
                    if w < 300 or h < 200:  # Skip small images (increased threshold)
                        continue
                except:
                    pass
            
            # Skip common icon/logo/banner patterns
            if any(skip in src_lower for skip in [
                "logo", "icon", "avatar", "button", "badge", "spinner", "social", "share", 
                "facebook", "twitter", "linkedin", "banner", "header", "nav", "navigation",
                "topbar", "top-bar", "site-logo", "brand", "favicon", "menu", "navbar"
            ]):
                continue
            
            # Skip screenshot service URLs
            if "screenshot" in src_lower or "microlink" in src_lower or "shot" in src_lower:
                print(f"[image]   ✗ Skipping screenshot service URL: {src[:60]}")
                continue
            
            # Resolve relative URLs
            if src.startswith("//"):
                parsed = urlparse(article_url)
                src = f"{parsed.scheme}:{src}"
            elif src.startswith("/"):
                parsed = urlparse(article_url)
                src = f"{parsed.scheme}://{parsed.netloc}{src}"
            elif not src.startswith("http"):
                continue
            
            # Must be a real image file
            if any(ext in src_lower for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]):
                if _validate_image_url(src, article_url):
                    print(f"[image] ✓✓✓ VALIDATED article content image: {src[:100]}")
                    return src
                else:
                    print(f"[image]   ✗ Content image failed validation, trying next...")
                    continue
    
    # Method 4: Try JSON-LD structured data (some sites use this)
    print(f"[image] Method 4: Checking JSON-LD structured data...")
    try:
        json_ld_scripts = soup.find_all("script", type="application/ld+json")
        for script in json_ld_scripts:
            try:
                data = json.loads(script.string)
                # Handle both dict and list of dicts
                if isinstance(data, list) and len(data) > 0:
                    data = data[0]
                if isinstance(data, dict):
                    # Check for image in various JSON-LD formats
                    image = data.get("image") or data.get("thumbnailUrl") or data.get("url")
                    if isinstance(image, dict):
                        image = image.get("url") or image.get("@id") or image.get("contentUrl")
                    if isinstance(image, list) and len(image) > 0:
                        image = image[0]
                        if isinstance(image, dict):
                            image = image.get("url") or image.get("@id") or image.get("contentUrl")
                    if image and isinstance(image, str) and image.startswith("http"):
                        image_lower = image.lower()
                        if "screenshot" not in image_lower and "microlink" not in image_lower and "shot" not in image_lower:
                            if any(ext in image_lower for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]) or "image" in image_lower:
                                if _validate_image_url(image, article_url):
                                    print(f"[image] ✓✓✓✓✓ VALIDATED JSON-LD image: {image[:100]}")
                                    return image
                                else:
                                    print(f"[image]   ✗ JSON-LD image failed validation, trying next...")
                                    continue
            except Exception as json_err:
                continue
    except Exception as json_ld_err:
        pass
    
    print(f"[image] ✗✗✗✗✗ NO FEATURED IMAGE FOUND - All methods exhausted for {article_url[:60]}")
    print(f"[image] Will fall back to screenshot service (full page screenshot)")
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

    # Download image with retry and validation
    content = None
    content_type = "image/jpeg"
    headers = HEADERS.copy()
    headers["User-Agent"] = random.choice(USER_AGENTS)
    
    for attempt in range(2):
        try:
            resp = requests.get(image_url, timeout=15, headers=headers, stream=True, allow_redirects=True)
            
            # Check for Cloudflare blocks
            if resp.status_code == 403:
                print(f"[image] ✗✗✗ Image URL blocked by Cloudflare (403)")
                return None
            if resp.status_code == 429:
                print(f"[image] ✗✗✗ Image URL rate limited (429)")
                return None
            
        resp.raise_for_status()
        content = resp.content
            content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
            
            # Validate content size
            if len(content) < 500:  # Too small, might be error page
                print(f"[image] ✗ Downloaded content too small ({len(content)} bytes), likely error page")
                if attempt == 0:
                    import time
                    time.sleep(2)
                    continue
                return None
            
            # Check if it's actually an image (not HTML error page)
            content_preview = content[:500].decode("utf-8", errors="ignore").lower()
            if any(error_indicator in content_preview for error_indicator in [
                "<html", "<!doctype", "error", "cloudflare", "access denied", 
                "403", "404", "500", "blocked", "banned", "error 1008"
            ]):
                print(f"[image] ✗✗✗ Downloaded content is HTML error page, not image")
                return None
            
            # Check image magic bytes
            if not (content.startswith(b"\xff\xd8\xff") or content.startswith(b"\x89PNG") or 
                    content.startswith(b"GIF8") or content.startswith(b"RIFF") or 
                    content.startswith(b"\x00\x00\x01\x00") or content.startswith(b"WEBP")):
                print(f"[image] ✗✗✗ Downloaded content is not a valid image (no magic bytes)")
                return None
            
            # Verify content type
            if "image/" not in content_type.lower() and not any(ext in image_url.lower() for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]):
                print(f"[image] ✗ Content-Type is not image: {content_type}")
                return None
            
            print(f"[image] ✓ Downloaded valid image: {len(content)} bytes, type: {content_type}")
            break
            
        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code in [403, 429]:
                print(f"[image] ✗✗✗ HTTP error {e.response.status_code} - blocked/rate limited")
                return None
            print(f"[image] download failed (attempt {attempt+1}/2) for {image_url}: {e}")
            if attempt == 1:
                return None
            import time
            time.sleep(2)
    except Exception as exc:
            print(f"[image] download failed (attempt {attempt+1}/2) for {image_url}: {exc}")
            if attempt == 1:
                return None
            import time
            time.sleep(2)
    
    if not content:
        print(f"[image] ✗✗✗ Failed to download valid image content")
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
            
            # Check if article already exists in DB and has no image_url - prioritize screenshot
            existing_has_image = False
            try:
                existing = supabase.table("articles").select("image_url").eq("link", link).limit(1).execute()
                if existing.data and len(existing.data) > 0:
                    existing_img = existing.data[0].get("image_url")
                    if existing_img and existing_img.strip():
                        existing_has_image = True
                        print(f"[article] Article exists in DB with image_url: {existing_img[:80] if len(existing_img) > 80 else existing_img}")
                    else:
                        print(f"[article] ⚠️  Article exists in DB but NO image_url - will prioritize screenshot!")
            except Exception as check_err:
                print(f"[article] Could not check existing article: {check_err}")
            
            # Method 0: Try RSS feed entry image first (fastest, most reliable)
            if not existing_has_image:  # Only try RSS if existing article has no image
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
            
            # Method 1: Try OG/featured image extraction (HIGHEST PRIORITY - gets actual article image, NOT full page screenshot)
            # Always try this first - it gets the actual article featured image, not a full page screenshot
            # This is CRITICAL to avoid full page screenshots
            if not uploaded_url:
                try:
                    print(f"[article] ========================================")
                    print(f"[article] STEP 1: Extracting featured/OG image from article...")
                    print(f"[article] (This gets the actual article image, NOT a full page screenshot)")
                    print(f"[article] ========================================")
            og_image = _extract_image_url(link)
                    if og_image:
                        print(f"[article] ✓✓✓ Extracted featured/OG image: {og_image[:100]}")
                        # Verify it's not a screenshot service URL
                        if "screenshot" not in og_image.lower() and "microlink" not in og_image.lower():
                            uploaded_url = _upload_image_to_supabase(og_image)
                            if uploaded_url:
                                print(f"[article] ✓✓✓✓✓ SUCCESS: Uploaded ACTUAL featured image: {uploaded_url[:100]}")
                                print(f"[article] This is the real article image, NOT a full page screenshot!")
                            else:
                                print(f"[article] ✗ Featured image upload failed, will try screenshot as last resort...")
                        else:
                            print(f"[article] ⚠️  Extracted URL is a screenshot service, skipping...")
                    else:
                        print(f"[article] ✗ No featured/OG image found in article HTML")
                        print(f"[article] Will try screenshot service as last resort (but this will be full page)")
                except Exception as og_err:
                    print(f"[article] ✗ Featured image extraction error: {og_err}")
                    import traceback
                    traceback.print_exc()
            
            # Method 2: Screenshot service DISABLED - causes full page screenshots and Cloudflare blocks
            # We now rely ONLY on actual OG/featured images extracted from articles
            # If no OG image found, we skip thumbnail (frontend will show default placeholder)
            # This prevents:
            # 1. Full page screenshots instead of thumbnails
            # 2. Cloudflare IP bans (Error 1008)
            # 3. White pages from screenshot service failures
            # 4. Screenshots of article titles instead of images
            
            # SCREENSHOT SERVICE DISABLED - Use default placeholder if no OG image found
            if not uploaded_url:
                print(f"[article] ⚠️  No featured image found - will use default placeholder on frontend")
                print(f"[article] This is better than a full page screenshot!")
                print(f"[article] Frontend will show default placeholder image instead of broken screenshot")
            
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
        # Use bytes directly, not BytesIO
        storage.upload(f"raw-feeds/{batch_id}", raw_bytes, file_options={"content-type": "application/json"})
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
        print(f"[articles] ========================================")
        print(f"[articles] ABOUT TO UPSERT TO DATABASE")
        print(f"[articles] ========================================")
        print(f"[articles] Total articles: {len(collected)}")
        print(f"[articles] Articles WITH image_url: {articles_with_images}")
        print(f"[articles] Articles WITHOUT image_url: {len(collected) - articles_with_images}")
        print(f"[articles] ========================================")
        for i, art in enumerate(collected[:5]):  # Log first 5
            img = art.get("image_url") or ""
            print(f"[articles] Article {i+1}: '{art.get('title', '')[:40]}'")
            print(f"[articles]   → image_url: {img[:100] if img else 'NONE/EMPTY'}")
            if img and "supabase.co" in img:
                print(f"[articles]   → ✓ Supabase storage URL detected")
        
        # Use upsert with ignore_duplicates=False to update existing rows
        # This ensures image_url gets updated even if article already exists
        print(f"[articles] Executing upsert with on_conflict='link', ignore_duplicates=False...")
        response = supabase.table("articles").upsert(
            collected,
            on_conflict="link",
            ignore_duplicates=False,  # Update existing rows instead of ignoring
        ).execute()
        inserted = len(response.data) if getattr(response, "data", None) else len(collected)
        print(f"[articles] ========================================")
        print(f"[articles] ✓✓✓ UPSERT COMPLETE: {inserted} records processed")
        print(f"[articles] ========================================")
        
        # Verify what was actually saved - query back from database
        if response.data:
            for i, saved in enumerate(response.data[:3]):
                saved_img = saved.get("image_url")
                print(f"[articles] Response article {i+1}: image_url = {saved_img[:100] if saved_img else 'NONE'}")
        
        # Double-check by querying database directly
        print(f"[articles] Verifying saved data in database...")
        for i, art in enumerate(collected[:3]):
            link = art.get("link")
            if link:
                try:
                    db_check = supabase.table("articles").select("id, title, image_url").eq("link", link).limit(1).execute()
                    if db_check.data:
                        db_img = db_check.data[0].get("image_url")
                        print(f"[articles] DB check {i+1}: '{art.get('title', '')[:30]}' -> image_url: {db_img[:80] if db_img else 'NONE/EMPTY'}")
                except Exception as db_err:
                    print(f"[articles] DB check failed for {link[:50]}: {db_err}")
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

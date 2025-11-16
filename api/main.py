# api/main.py
from fastapi import FastAPI, BackgroundTasks, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
import subprocess, sys, os, json, pathlib, re
from pathlib import Path
from datetime import datetime
from typing import Optional
from html import unescape

app = FastAPI(title="AI-CTI API")

# allow local UI calls
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    """Root endpoint for health check"""
    return {
        "status": "ok",
        "service": "AI-CTI API",
        "docs": "/docs",
        "endpoints": {
            "results": "/results",
            "fetch_live": "/fetch_live (POST)",
            "docs": "/docs"
        }
    }

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INGEST = os.path.join(BASE, "data_ingest", "ingest.py")
PREPROC = os.path.join(BASE, "data_ingest", "preprocess.py")
IOC = os.path.join(BASE, "utils", "ioc_extractor.py")
CLUST = os.path.join(BASE, "models", "clustering.py")
LIVE_SUPABASE = os.path.join(BASE, "data_ingest", "live_ingest_supabase.py")
RESULTS_DIR = Path(BASE) / "data_results"
PROC_DIR = Path(BASE) / "data_ingest" / "processed"

TAG_RE = re.compile(r"<[^>]+>")
SAVED_TABLE = "saved_briefings"


def clean_text(value: Optional[str]) -> str:
    if not value:
        return ""
    text = unescape(value)
    text = TAG_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
SUPABASE_ENABLED = False
supabase_client = None

try:
    if SUPABASE_URL and SUPABASE_KEY:
        from supabase import create_client as create_supabase_client

        supabase_client = create_supabase_client(SUPABASE_URL, SUPABASE_KEY)
        # Test connection (non-blocking, don't crash if it fails)
        try:
            # Quick test - don't wait too long
            supabase_client.table("articles").select("id").limit(1).execute()
            SUPABASE_ENABLED = True
            print("[supabase] Client initialized successfully")
        except Exception as test_err:
            print(f"[supabase] Connection test failed (will retry on first request): {test_err}")
            # Don't disable completely - might work on actual requests
            SUPABASE_ENABLED = True  # Allow it to try on actual requests
            # supabase_client is still set, just test failed
    else:
        print("[supabase] Missing SUPABASE_URL or SUPABASE_KEY, disabling Supabase")
        SUPABASE_ENABLED = False
        supabase_client = None
except Exception as supa_exc:
    print(f"[supabase] Client initialization failed (non-fatal): {supa_exc}")
    import traceback
    traceback.print_exc()
    # Don't crash - allow server to start without Supabase
    SUPABASE_ENABLED = False
    supabase_client = None


def run_cmd(cmd):
    # run a python script via same interpreter
    print(f"[api] ========================================")
    print(f"[api] EXECUTING COMMAND: {cmd}")
    print(f"[api] ========================================")
    
    # Check if file exists
    if not os.path.exists(cmd):
        error_msg = f"[api] ERROR: Script not found: {cmd}"
        print(error_msg)
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": error_msg
        }
    
    print(f"[api] Script exists, starting subprocess...")
    
    # Use Popen to stream output in real-time
    try:
        proc = subprocess.Popen(
            [sys.executable, cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Combine stderr into stdout
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True,
            env=os.environ.copy()  # Pass environment variables
        )
        
        # Print output line by line in real-time
        stdout_lines = []
        for line in proc.stdout:
            line = line.rstrip()
            if line:  # Only print non-empty lines
                print(f"[ingest] {line}")
                stdout_lines.append(line)
        
        proc.wait()
        
        if proc.returncode != 0:
            print(f"[api] WARNING: Script exited with code {proc.returncode}")
        else:
            print(f"[api] Script completed successfully (exit code 0)")
        
        return {
            "returncode": proc.returncode,
            "stdout": "\n".join(stdout_lines),
            "stderr": ""
        }
    except Exception as e:
        error_msg = f"[api] ERROR running command: {e}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": error_msg
        }


@app.post("/ingest")
def ingest(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_cmd, INGEST)
    return {"status": "ingest started"}


@app.post("/preprocess")
def preprocess(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_cmd, PREPROC)
    return {"status": "preprocess started"}


@app.post("/extract_iocs")
def extract_iocs(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_cmd, IOC)
    return {"status": "ioc extraction started"}


@app.post("/analyze")
def analyze(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_cmd, CLUST)
    return {"status": "analysis started"}


@app.get("/results")
def results():
    try:
        out = {}

        if SUPABASE_ENABLED and supabase_client:
            # prefer live articles from Supabase
            try:
                # Sort by published_at DESC (latest first), fallback to fetched_at if published_at is null
                # Get all articles, sort in Python for better control
                articles_resp = supabase_client.table("articles").select(
                    "title,description,link,source,source_name,image_url,published_at,fetched_at"
                ).limit(200).execute()
                
                # Filter out ZDNet Security and other non-cybersec sources
                articles_list = articles_resp.data or []
                filtered_articles = []
                excluded_sources = ["zdnet", "zdnet security"]
                for article in articles_list:
                    source_name = (article.get("source_name") or "").lower()
                    if any(excluded in source_name for excluded in excluded_sources):
                        continue
                    filtered_articles.append(article)
                articles_list = filtered_articles
                
                # Sort: published_at DESC first, then fetched_at DESC for nulls
                # Convert to datetime for proper sorting
                from datetime import datetime
                
                def get_sort_date(article):
                    """Get sortable datetime from article"""
                    date_str = article.get("published_at") or article.get("fetched_at")
                    if not date_str:
                        return datetime(1970, 1, 1)
                    try:
                        # Handle ISO format strings
                        if isinstance(date_str, str):
                            # Clean up the string
                            date_str = date_str.replace('Z', '+00:00')
                            # Try parsing with fromisoformat
                            if '+' in date_str or '-' in date_str[-6:]:
                                # Has timezone
                                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            else:
                                # No timezone, assume UTC
                                return datetime.fromisoformat(date_str)
                        # If already a datetime object
                        if isinstance(date_str, datetime):
                            return date_str
                        return datetime(1970, 1, 1)
                    except Exception as e:
                        print(f"[sort] Failed to parse date {date_str}: {e}")
                        return datetime(1970, 1, 1)
                
                articles_list.sort(key=get_sort_date, reverse=True)

                # Deduplicate by canonical link/title to prevent duplicate cards
                # Use fuzzy matching for similar titles (e.g., "DoorDash hit by yet another data breach" vs "DoorDash hit by new data breach")
                def normalize_title(title):
                    """Normalize title for fuzzy matching"""
                    if not title:
                        return ""
                    # Remove common words, normalize case, remove special chars
                    title = title.lower().strip()
                    # Remove common prefixes/suffixes
                    title = re.sub(r'\b(yet another|new|another|latest|recent)\b', '', title)
                    # Remove special chars, keep only alphanumeric and spaces
                    title = re.sub(r'[^\w\s]', '', title)
                    # Normalize whitespace
                    title = re.sub(r'\s+', ' ', title).strip()
                    # Take first 50 chars for comparison (most important part)
                    return title[:50]
                
                def normalize_link(link):
                    """Normalize link by removing query params and fragments"""
                    if not link:
                        return ""
                    try:
                        from urllib.parse import urlparse, urlunparse
                        parsed = urlparse(link.strip().lower())
                        # Remove query and fragment
                        normalized = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
                        return normalized
                    except:
                        return link.strip().lower()
                
                seen_keys = set()
                seen_normalized_titles = {}  # normalized_title -> first article
                unique_articles = []
                for row in articles_list:
                    link = row.get("link") or ""
                    title = row.get("title") or ""
                    source = (row.get("source_name") or row.get("source") or "").lower()
                    
                    # First check exact link match
                    normalized_link = normalize_link(link)
                    if normalized_link and normalized_link in seen_keys:
                        print(f"[dedup] Skipping duplicate link: {link[:80]}")
                        continue
                    
                    # Then check fuzzy title match (same source, similar title)
                    normalized_title = normalize_title(title)
                    if normalized_title and source:
                        title_key = f"{normalized_title}::{source}"
                        if title_key in seen_normalized_titles:
                            existing = seen_normalized_titles[title_key]
                            existing_title = existing.get("title", "")
                            # If titles are very similar (>80% similarity), skip
                            if normalized_title and len(normalized_title) > 20:
                                # Simple similarity check: if normalized titles match or one is substring of other
                                if normalized_title == normalize_title(existing_title) or \
                                   (len(normalized_title) > 30 and len(normalize_title(existing_title)) > 30 and
                                    (normalized_title in normalize_title(existing_title) or 
                                     normalize_title(existing_title) in normalized_title)):
                                    print(f"[dedup] Skipping similar title: '{title[:60]}' (similar to '{existing_title[:60]}')")
                                    continue
                    
                    # Add to seen sets
                    if normalized_link:
                        seen_keys.add(normalized_link)
                    if normalized_title and source:
                        seen_normalized_titles[f"{normalized_title}::{source}"] = row
                    
                    unique_articles.append(row)

                articles_list = unique_articles[:40]  # Take top 40 unique entries
                feeds = []
                for row in articles_list:
                    image_url = row.get("image_url") or ""
                    # Debug: log first few articles' image URLs
                    if len(feeds) < 3:
                        print(f"[api] Article '{row.get('title', '')[:50]}' image_url: {image_url[:100] if image_url else 'MISSING'}")
                    feeds.append({
                        "title": row.get("title") or "",
                        "description": clean_text(row.get("description") or ""),
                        "link": row.get("link") or "",
                        "source": row.get("source_name") or row.get("source") or "Unknown",
                        "raw_source": row.get("source") or "",
                        "image": image_url,
                        "image_url": image_url,
                        "published_at": row.get("published_at"),
                        "fetched_at": row.get("fetched_at"),
                    })
                out["feeds"] = feeds
                print(f"[api] Fetched {len(feeds)} articles from Supabase")
                # Count how many have image_url
                with_images = sum(1 for f in feeds if f.get("image_url") and f.get("image_url") != "")
                print(f"[api] Articles with image_url: {with_images}/{len(feeds)}")
            except Exception as supa_err:
                print(f"[api] Supabase fetch failed: {supa_err}")
                import traceback
                traceback.print_exc()
                out["feeds"] = []
        else:
            out["feeds"] = []

        if not out["feeds"]:
            # Fall back to legacy JSON files if Supabase unavailable
            feeds = []
            try:
                if PROC_DIR.exists():
                    for proc_file in PROC_DIR.glob("*.json"):
                        try:
                            with open(proc_file, encoding="utf-8") as f:
                                doc = json.load(f)
                                if doc.get("link"):
                                    text = doc.get("text", "")
                                    description = text[:200] + "..." if len(text) > 200 else text
                                    feeds.append({
                                        "title": doc.get("title", proc_file.stem),
                                        "link": doc.get("link", ""),
                                        "source": doc.get("source", "Unknown"),
                                        "description": description
                                    })
                        except Exception as e:
                            print(f"[api] Error reading {proc_file}: {e}")
                            continue
            except Exception as e:
                print(f"[api] Error processing feeds: {e}")

            seen_links = set()
            unique_feeds = []
            for feed in feeds:
                if feed.get("link") and feed["link"] not in seen_links:
                    seen_links.add(feed["link"])
                    unique_feeds.append(feed)
            out["feeds"] = unique_feeds[:20]

        # IOCs & clusters: prefer Supabase aggregation when available
        if SUPABASE_ENABLED and supabase_client:
            try:
                iocs_resp = supabase_client.table("iocs").select(
                    "type,value,file,created_at"
                ).order("created_at", desc=True).limit(200).execute()
                out["iocs"] = iocs_resp.data or []
            except Exception as ioc_err:
                print(f"[api] Supabase IOC fetch failed: {ioc_err}")
                out["iocs"] = []
        else:
            out["iocs"] = []

        if not out["iocs"]:
            out_path = RESULTS_DIR
            try:
                if (out_path / "iocs_results.json").exists():
                    out["iocs"] = json.loads((out_path / "iocs_results.json").read_text(encoding="utf-8"))
                else:
                    out["iocs"] = []
            except Exception as e:
                print(f"[api] Error loading iocs_results.json: {e}")
                out["iocs"] = []

        if SUPABASE_ENABLED and supabase_client:
            out["clusters"] = {}  # reserved for future Supabase-based clustering
        else:
            out_path = RESULTS_DIR
            try:
                if (out_path / "clusters.json").exists():
                    out["clusters"] = json.loads((out_path / "clusters.json").read_text(encoding="utf-8"))
                else:
                    out["clusters"] = {}
            except Exception as e:
                print(f"[api] Error loading clusters.json: {e}")
                out["clusters"] = {}

        return out

    except Exception as e:
        print(f"[api] Error in /results endpoint: {e}")
        import traceback
        traceback.print_exc()
        return {
            "iocs": [],
            "clusters": {},
            "feeds": [],
            "error": str(e)
        }


@app.get("/article")
def article(link: str):
    if not link:
        raise HTTPException(status_code=400, detail="link query parameter is required")

    try:
        article_payload = None

        if SUPABASE_ENABLED and supabase_client:
            try:
                article_resp = supabase_client.table("articles").select(
                    "title,description,link,source,source_name,image_url,published_at,fetched_at"
                ).eq("link", link).limit(1).execute()

                row = (article_resp.data or [None])[0]
                if row:
                    article_payload = {
                        "title": row.get("title") or "",
                        "description": clean_text(row.get("description") or ""),
                        "link": row.get("link") or "",
                        "source": row.get("source_name") or row.get("source") or "Unknown",
                        "raw_source": row.get("source") or "",
                        "image": row.get("image_url") or "",
                        "image_url": row.get("image_url") or "",
                        "published_at": row.get("published_at"),
                        "fetched_at": row.get("fetched_at"),
                    }
            except Exception as supa_err:
                print(f"[api] Supabase single fetch failed: {supa_err}")

        if not article_payload:
            # Fall back to cached results
            feed_data = results().get("feeds", [])
            for item in feed_data:
                if item.get("link") == link:
                    article_payload = item
                    break

        if not article_payload:
            return {"article": None, "error": "Article not found"}

        article_payload = enrich_article(article_payload)
        article_payload["highlights"] = build_article_highlights(article_payload)
        
        # Add AI features
        article_payload["ai_summary"] = generate_ai_summary(
            article_payload.get("description", "") or article_payload.get("title", "")
        )
        article_payload["ai_categories"] = auto_categorize_article(article_payload)
        
        # Get recommendations from all feeds
        all_feeds = results().get("feeds", [])
        article_payload["ai_recommendations"] = get_ai_recommendations(article_payload, all_feeds, limit=3)
        
        return {"article": article_payload, "error": None}

    except HTTPException:
        raise
    except Exception as exc:
        print(f"[api] Error in /article endpoint: {exc}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal error retrieving article")


@app.post("/fetch_live")
def fetch_live(background_tasks: BackgroundTasks):
    """Fetch live feeds and upload to Supabase"""
    import sys
    sys.stdout.flush()  # Force flush to ensure logs appear immediately
    
    print("[api] ========================================")
    print("[api] /fetch_live endpoint called - starting ingestion")
    print(f"[api] LIVE_SUPABASE path: {LIVE_SUPABASE}")
    print(f"[api] File exists: {os.path.exists(LIVE_SUPABASE)}")
    print("[api] ========================================")
    sys.stdout.flush()
    
    # Clean old data first, then fetch new
    if SUPABASE_ENABLED and supabase_client:
        print("[api] Adding cleanup_old_data task")
        background_tasks.add_task(cleanup_old_data)
    else:
        print("[api] WARNING: Supabase not enabled, skipping cleanup")
    
    print(f"[api] Adding ingestion task: {LIVE_SUPABASE}")
    sys.stdout.flush()
    background_tasks.add_task(run_cmd, LIVE_SUPABASE)
    
    print("[api] Background tasks queued, returning response")
    sys.stdout.flush()
    return {"status": "live feed ingestion started", "script_path": LIVE_SUPABASE, "exists": os.path.exists(LIVE_SUPABASE)}


def cleanup_old_data():
    """Delete articles older than 7 days and keep max 200 recent articles"""
    print("[cleanup] Starting old data cleanup...")
    if not SUPABASE_ENABLED or not supabase_client:
        print("[cleanup] Supabase not enabled, skipping cleanup")
        return
    try:
        from datetime import datetime, timedelta, timezone
        
        # Delete articles older than 7 days
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        old_articles = supabase_client.table("articles").select("id").lt("fetched_at", cutoff_date).execute()
        if old_articles.data:
            ids_to_delete = [row["id"] for row in old_articles.data]
            for article_id in ids_to_delete:
                try:
                    supabase_client.table("articles").delete().eq("id", article_id).execute()
                except Exception as e:
                    print(f"[cleanup] Failed to delete article {article_id}: {e}")
            print(f"[cleanup] Deleted {len(ids_to_delete)} old articles (older than 7 days)")
        
        # Keep only latest 200 articles (delete rest)
        all_articles = supabase_client.table("articles").select("id").order("fetched_at", desc=True).execute()
        if all_articles.data and len(all_articles.data) > 200:
            ids_to_keep = {row["id"] for row in all_articles.data[:200]}
            ids_to_delete = [row["id"] for row in all_articles.data if row["id"] not in ids_to_keep]
            for article_id in ids_to_delete:
                try:
                    supabase_client.table("articles").delete().eq("id", article_id).execute()
                except Exception as e:
                    print(f"[cleanup] Failed to delete article {article_id}: {e}")
            print(f"[cleanup] Deleted {len(ids_to_delete)} excess articles (kept latest 200)")
        
        # Clean old IOCs (older than 30 days)
        ioc_cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        old_iocs = supabase_client.table("iocs").select("id").lt("created_at", ioc_cutoff).execute()
        if old_iocs.data:
            ioc_ids = [row["id"] for row in old_iocs.data]
            for ioc_id in ioc_ids:
                try:
                    supabase_client.table("iocs").delete().eq("id", ioc_id).execute()
                except Exception as e:
                    print(f"[cleanup] Failed to delete IOC {ioc_id}: {e}")
            print(f"[cleanup] Deleted {len(ioc_ids)} old IOCs (older than 30 days)")
            
    except Exception as e:
        print(f"[cleanup] Error during cleanup: {e}")
        import traceback
        traceback.print_exc()


@app.post("/run_all")
def run_all():
    """Run the full pipeline synchronously: fetch_live -> preprocess -> extract_iocs -> analyze"""
    commands = [LIVE_SUPABASE, PREPROC, IOC, CLUST]
    results = []
    for cmd in commands:
        print("[run_all] running", cmd)
        proc = subprocess.run([sys.executable, cmd], capture_output=True, text=True)
        results.append({
            "cmd": cmd,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr
        })
        # if one step failed, stop and return partial results
        if proc.returncode != 0:
            return {"status": "error", "stage": cmd, "results": results}
    return {"status": "ok", "results": results}


# Optional scheduler support
ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "false").lower() == "true"

if ENABLE_SCHEDULER:
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        scheduler = BackgroundScheduler()

        def scheduled_fetch():
            print("[scheduler] Running scheduled feed fetch")
            run_cmd(LIVE_SUPABASE)
            # Optionally run full pipeline
            # run_cmd(PREPROC)
            # run_cmd(IOC)
            # run_cmd(CLUST)

        # Schedule every 30 minutes
        scheduler.add_job(
            scheduled_fetch,
            trigger=IntervalTrigger(minutes=30),
            id='fetch_live_feeds',
            name='Fetch live threat feeds',
            replace_existing=True
        )

        scheduler.start()
        print("[scheduler] Started - will fetch feeds every 30 minutes")
    except ImportError:
        print("[scheduler] APScheduler not installed. Install with: pip install apscheduler")
    except Exception as e:
        print(f"[scheduler] Error starting scheduler: {e}")


@app.on_event("shutdown")
def shutdown_event():
    if ENABLE_SCHEDULER and 'scheduler' in globals():
        scheduler.shutdown()
        print("[scheduler] Stopped")


def build_article_highlights(article):
    """Generate brief highlight points for an article payload."""
    from datetime import datetime

    highlights = []
    if not article:
        return highlights

    title = article.get("title") or ""
    description = article.get("description") or ""
    source = article.get("source") or article.get("source_name") or article.get("raw_source") or ""
    published = article.get("published_at") or article.get("fetched_at")

    if title:
        highlights.append(title)
    if description:
        highlights.append(description[:220] + "…" if len(description) > 220 else description)
    if source:
        highlights.append(f"Source: {source}")
    if published:
        try:
            ts = published
            if isinstance(ts, str):
                ts = ts.replace('Z', '+00:00')
                stamp = datetime.fromisoformat(ts)
            elif isinstance(ts, datetime):
                stamp = ts
            else:
                stamp = None
            if stamp:
                highlights.append(f"Published: {stamp.strftime('%d %b %Y, %H:%M UTC')}")
        except Exception:
            highlights.append(f"Published: {published}")

    return highlights[:4]

RISK_LEVELS = ["Critical", "High", "Medium", "Low"]
RISK_KEYWORDS = {
    "Critical": [
        "zero-day",
        "supply chain breach",
        "nation-state",
        "mass exploitation",
        "critical vulnerability",
        "remote code execution",
        "rce",
    ],
    "High": [
        "ransomware",
        "data breach",
        "leak",
        "exploit",
        "zero day",
        "worm",
        "botnet",
        "credential theft",
    ],
    "Medium": [
        "phishing",
        "malware",
        "trojan",
        "backdoor",
        "denial of service",
        "ddos",
    ],
}
SUSPICIOUS_TLDS = {"ru", "cn", "su", "top", "xyz", "tk", "ga", "ml", "cf"}
SAVED_TABLE = "saved_briefings"


def classify_article(article):
    text = " ".join(
        filter(
            None,
            [
                article.get("title"),
                article.get("description"),
                article.get("summary"),
            ],
        )
    ).lower()

    severity = "Low"
    score = 5
    reasons = []
    tags = set()

    for level in RISK_LEVELS:
        for keyword in RISK_KEYWORDS.get(level, []):
            if keyword in text:
                reasons.append(f"Contains keyword: {keyword}")
                tags.add(keyword.replace(" ", "-"))
                if RISK_LEVELS.index(level) <= RISK_LEVELS.index(severity):
                    severity = level
                score = max(score, 90 if level == "Critical" else 70 if level == "High" else 50)

    if "cve-" in text:
        reasons.append("Mentions CVE identifier")
        tags.add("cve")
        score = max(score, 65)
        if severity in ("Low", "Medium"):
            severity = "Medium"

    if article.get("source_name") and any(word in article["source_name"].lower() for word in ["cisa", "msrc", "cert"]):
        reasons.append("Originates from high-trust advisory source")
        score = max(score, 60)
        if severity == "Low":
            severity = "Medium"

    sentiment = "threat" if severity in ("Critical", "High") else "watch"

    return {
        "level": severity,
        "score": score,
        "reasons": reasons[:4],
        "tags": sorted(tags)[:6],
        "sentiment": sentiment,
    }


def enrich_article(article):
    risk = classify_article(article)
    article["risk"] = risk
    article.setdefault("tags", []).extend(risk["tags"])
    article["tags"] = sorted(set(filter(None, article["tags"])))
    return article


def enrich_ioc_record(record):
    enrichment = {
        "severity": "Medium",
        "context": [],
    }
    value = (record.get("value") or "").lower()
    ioc_type = (record.get("type") or "").lower()

    if ioc_type == "ip" and value:
        if value.startswith("10.") or value.startswith("192.168") or value.startswith("172.16"):
            enrichment["severity"] = "Low"
            enrichment["context"].append("Private address space")
        else:
            enrichment["severity"] = "High"
            enrichment["context"].append("Public IP, potential attacker infrastructure")

    if ioc_type == "domain" and value:
        tld = value.split('.')[-1]
        if tld in SUSPICIOUS_TLDS:
            enrichment["severity"] = "High"
            enrichment["context"].append(f"Suspicious TLD: .{tld}")

    if ioc_type == "cve" and value:
        enrichment["severity"] = "High"
        enrichment["context"].append("Actionable CVE identifier")

    record["enrichment"] = enrichment
    return record


@app.get("/saved")
def list_saved(client_id: str):
    if not client_id:
        raise HTTPException(status_code=400, detail="client_id is required")

    if not SUPABASE_ENABLED or not supabase_client:
        return {"items": []}

    try:
        resp = (
            supabase_client
            .table(SAVED_TABLE)
            .select("client_id,link,title,source,image_url,risk_level,risk_score,saved_at")
            .eq("client_id", client_id)
            .order("saved_at", desc=True)
            .limit(50)
            .execute()
        )
        return {"items": resp.data or []}
    except Exception as exc:
        print(f"[saved] fetch failed: {exc}")
        return {"items": []}


@app.post("/saved")
def upsert_saved(payload: dict = Body(...)):
    if not payload:
        raise HTTPException(status_code=400, detail="Missing request body")

    client_id = payload.get("client_id")
    link = payload.get("link")
    if not client_id or not link:
        raise HTTPException(status_code=400, detail="client_id and link are required")

    if not SUPABASE_ENABLED or not supabase_client:
        print(f"[saved] ERROR: Supabase not enabled. SUPABASE_ENABLED={SUPABASE_ENABLED}, supabase_client={supabase_client is not None}")
        raise HTTPException(status_code=503, detail="Supabase not configured")

    record = {
        "client_id": client_id,
        "link": link,
        "title": payload.get("title") or "",
        "source": payload.get("source") or payload.get("source_name") or "Unknown",
        "image_url": payload.get("image_url") or "",
        "risk_level": payload.get("risk_level") or payload.get("risk", {}).get("level"),
        "risk_score": payload.get("risk_score") or payload.get("risk", {}).get("score"),
        "saved_at": datetime.utcnow().isoformat(),
    }

    try:
        print(f"[saved] Attempting to upsert record: client_id={client_id}, link={link[:80]}, table={SAVED_TABLE}")
        result = supabase_client.table(SAVED_TABLE).upsert(record, on_conflict="client_id,link").execute()
        print(f"[saved] ✓ Successfully saved briefing: {link[:80]}")
        return {"status": "saved", "item": record}
    except Exception as exc:
        print(f"[saved] ✗ upsert failed: {exc}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to save briefing: {str(exc)}")


@app.delete("/saved")
def delete_saved(client_id: str, link: str):
    if not client_id or not link:
        raise HTTPException(status_code=400, detail="client_id and link are required")

    if not SUPABASE_ENABLED or not supabase_client:
        raise HTTPException(status_code=503, detail="Supabase not configured")

    try:
        supabase_client.table(SAVED_TABLE).delete().eq("client_id", client_id).eq("link", link).execute()
        return {"status": "removed"}
    except Exception as exc:
        print(f"[saved] delete failed: {exc}")
        raise HTTPException(status_code=500, detail="Failed to remove saved briefing")


@app.get("/export/pdf")
def export_pdf(client_id: str):
    """Generate PDF report of saved briefings"""
    if not client_id:
        raise HTTPException(status_code=400, detail="client_id is required")

    if not SUPABASE_ENABLED or not supabase_client:
        raise HTTPException(status_code=503, detail="Supabase not configured")

    try:
        # Fetch saved briefings
        resp = (
            supabase_client
            .table(SAVED_TABLE)
            .select("*")
            .eq("client_id", client_id)
            .order("saved_at", desc=True)
            .execute()
        )
        items = resp.data or []

        if not items:
            raise HTTPException(status_code=404, detail="No saved briefings found")

        # Generate PDF using reportlab
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
            from reportlab.lib.enums import TA_LEFT, TA_CENTER
            from io import BytesIO

            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
            story = []

            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#1a1a1a'),
                spaceAfter=30,
                alignment=TA_CENTER
            )
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=16,
                textColor=colors.HexColor('#1a1a1a'),
                spaceAfter=12,
                spaceBefore=20
            )
            normal_style = ParagraphStyle(
                'CustomNormal',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor('#4b5563'),
                leading=14
            )

            # Title
            story.append(Paragraph("AI-CTI Threat Intelligence Briefing", title_style))
            story.append(Spacer(1, 0.2*inch))
            story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", normal_style))
            story.append(Paragraph(f"Total Briefings: {len(items)}", normal_style))
            story.append(Spacer(1, 0.3*inch))

            # Add each briefing
            for idx, item in enumerate(items, 1):
                story.append(Paragraph(f"{idx}. {item.get('title', 'Untitled')}", heading_style))
                
                data = [
                    ['Source:', item.get('source', 'Unknown')],
                    ['Risk Level:', item.get('risk_level', 'Unknown')],
                    ['Saved:', item.get('saved_at', '')[:10] if item.get('saved_at') else 'Unknown'],
                ]
                if item.get('link'):
                    data.append(['Link:', item.get('link', '')[:80] + '...' if len(item.get('link', '')) > 80 else item.get('link', '')])

                table = Table(data, colWidths=[1.5*inch, 4.5*inch])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1a1a1a')),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
                ]))
                story.append(table)
                story.append(Spacer(1, 0.2*inch))

                if idx < len(items):
                    story.append(PageBreak())

            doc.build(story)
            buffer.seek(0)
            from fastapi.responses import Response
            return Response(content=buffer.read(), media_type="application/pdf", headers={
                "Content-Disposition": f'attachment; filename="ai-cti-briefings-{datetime.now().strftime("%Y-%m-%d")}.pdf"'
            })

        except ImportError:
            # Fallback: return JSON if reportlab not installed
            print("[export/pdf] reportlab not installed, returning JSON")
            return {
                "items": items,
                "generated_at": datetime.now().isoformat(),
                "format": "json",
                "note": "Install reportlab for PDF generation: pip install reportlab"
            }

    except HTTPException:
        raise
    except Exception as exc:
        print(f"[export/pdf] Error: {exc}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(exc)}")


def generate_ai_summary(text: str, max_length: int = 150) -> str:
    """Generate AI-powered summary of article text"""
    if not text or len(text) < 50:
        return text or ""
    
    # Simple extractive summarization (can be replaced with LLM API)
    sentences = text.split('. ')
    if len(sentences) <= 2:
        return text
    
    # Take first sentence and key sentences with important keywords
    important_keywords = ['breach', 'attack', 'vulnerability', 'exploit', 'malware', 'ransomware', 'critical', 'zero-day']
    key_sentences = [sentences[0]]
    
    for sentence in sentences[1:]:
        if any(keyword in sentence.lower() for keyword in important_keywords):
            key_sentences.append(sentence)
            if len('. '.join(key_sentences)) > max_length:
                break
    
    summary = '. '.join(key_sentences)
    if len(summary) > max_length:
        summary = summary[:max_length].rsplit(' ', 1)[0] + '...'
    else:
        summary += '.'
    
    return summary


def get_ai_recommendations(current_article: dict, all_articles: list, limit: int = 3) -> list:
    """Get AI-powered article recommendations"""
    if not current_article or not all_articles:
        return []
    
    current_title = (current_article.get('title') or '').lower()
    current_desc = (current_article.get('description') or '').lower()
    current_link = current_article.get('link', '')
    
    # Extract keywords from current article
    keywords = set()
    for word in (current_title + ' ' + current_desc).split():
        word = word.lower().strip('.,!?;:()[]{}')
        if len(word) > 4 and word not in ['that', 'this', 'with', 'from', 'have', 'been', 'were', 'their']:
            keywords.add(word)
    
    # Score other articles by keyword overlap
    scored = []
    for article in all_articles:
        if article.get('link') == current_link:
            continue
        
        article_text = ((article.get('title') or '') + ' ' + (article.get('description') or '')).lower()
        article_keywords = set(word.lower().strip('.,!?;:()[]{}') for word in article_text.split() if len(word) > 4)
        
        overlap = len(keywords & article_keywords)
        if overlap > 0:
            scored.append((overlap, article))
    
    # Sort by score and return top recommendations
    scored.sort(key=lambda x: x[0], reverse=True)
    return [article for _, article in scored[:limit]]


def auto_categorize_article(article: dict) -> list:
    """Auto-categorize article based on content"""
    title = (article.get('title') or '').lower()
    desc = (article.get('description') or '').lower()
    text = title + ' ' + desc
    
    categories = []
    
    # Attack type categories
    if any(word in text for word in ['ransomware', 'lockbit', 'blackcat', 'conti']):
        categories.append('Ransomware')
    if any(word in text for word in ['phishing', 'spear', 'email', 'credential']):
        categories.append('Phishing')
    if any(word in text for word in ['ddos', 'distributed denial']):
        categories.append('DDoS')
    if any(word in text for word in ['apt', 'nation-state', 'state-sponsored']):
        categories.append('APT')
    if any(word in text for word in ['malware', 'trojan', 'backdoor', 'rootkit']):
        categories.append('Malware')
    
    # Vulnerability categories
    if any(word in text for word in ['cve', 'vulnerability', 'exploit', 'patch']):
        categories.append('Vulnerability')
    if 'zero-day' in text:
        categories.append('Zero-Day')
    
    # Impact categories
    if any(word in text for word in ['breach', 'data leak', 'exposed', 'stolen']):
        categories.append('Data Breach')
    if any(word in text for word in ['critical', 'severe', 'urgent']):
        categories.append('Critical')
    
    # Technology categories
    if any(word in text for word in ['windows', 'microsoft', 'azure', 'office']):
        categories.append('Microsoft')
    if any(word in text for word in ['linux', 'ubuntu', 'debian', 'redhat']):
        categories.append('Linux')
    if any(word in text for word in ['cloud', 'aws', 'azure', 'gcp']):
        categories.append('Cloud')
    if any(word in text for word in ['iot', 'device', 'embedded']):
        categories.append('IoT')
    
    return categories[:5]  # Return max 5 categories

# api/main.py
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import subprocess, sys, os, json, pathlib
from pathlib import Path

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
    print("[api] running", cmd)
    proc = subprocess.run([sys.executable, cmd], capture_output=True, text=True)
    return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


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
                
                # Sort: published_at DESC first, then fetched_at DESC for nulls
                # Convert to datetime for proper sorting
                from datetime import datetime
                articles_list = articles_resp.data or []
                
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
                articles_list = articles_list[:40]  # Take top 40
                feeds = []
                for row in articles_list:
                    feeds.append({
                        "title": row.get("title") or "",
                        "description": row.get("description") or "",
                        "link": row.get("link") or "",
                        "source": row.get("source_name") or row.get("source") or "Unknown",
                        "raw_source": row.get("source") or "",
                        "image": row.get("image_url") or "",
                        "image_url": row.get("image_url") or "",
                        "published_at": row.get("published_at"),
                        "fetched_at": row.get("fetched_at"),
                    })
                out["feeds"] = feeds
                print(f"[api] Fetched {len(feeds)} articles from Supabase")
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
                        "description": row.get("description") or "",
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
    # Clean old data first, then fetch new
    if SUPABASE_ENABLED and supabase_client:
        background_tasks.add_task(cleanup_old_data)
    background_tasks.add_task(run_cmd, LIVE_SUPABASE)
    return {"status": "live feed ingestion started"}


def cleanup_old_data():
    """Delete articles older than 7 days and keep max 200 recent articles"""
    if not SUPABASE_ENABLED or not supabase_client:
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

# api/main.py
from fastapi import FastAPI, BackgroundTasks
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
        SUPABASE_ENABLED = True
except Exception as supa_exc:
    print(f"[supabase] client disabled: {supa_exc}")
    SUPABASE_ENABLED = False


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
                articles_resp = supabase_client.table("articles").select(
                    "title,description,link,source,source_name,image_url,published_at,fetched_at"
                ).order("fetched_at", desc=True).limit(40).execute()
                feeds = []
                for row in articles_resp.data or []:
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


@app.post("/fetch_live")
def fetch_live(background_tasks: BackgroundTasks):
    """Fetch live feeds and upload to Supabase"""
    background_tasks.add_task(run_cmd, LIVE_SUPABASE)
    return {"status": "live feed ingestion started"}


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

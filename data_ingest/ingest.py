import os, json, requests
from bs4 import BeautifulSoup
from datetime import datetime
import tempfile

# Supabase client (optional - if env vars are set, use Supabase; otherwise fallback to local)
try:
    from supabase import create_client
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "raw-feeds")
    USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)
    if USE_SUPABASE:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("[ingest] Using Supabase storage")
    else:
        print("[ingest] Supabase not configured, using local storage")
        supabase = None
except Exception as e:
    print("[ingest] Supabase not available:", e)
    USE_SUPABASE = False
    supabase = None

RAW = os.path.join(os.path.dirname(__file__), "raw")
os.makedirs(RAW, exist_ok=True)

def save_json(name, data, use_supabase=None):
    """Save JSON to Supabase bucket or local file"""
    if use_supabase is None:
        use_supabase = USE_SUPABASE
    
    if use_supabase and supabase:
        # Upload to Supabase
        fname = f"{name}.json"
        try:
            # Write to temp file first
            tmp = tempfile.gettempdir()
            local_path = os.path.join(tmp, fname)
            with open(local_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Upload to Supabase
            with open(local_path, "rb") as fh:
                res = supabase.storage.from_(SUPABASE_BUCKET).upload(fname, fh, file_options={"upsert": "true"})
            print("[ingest] uploaded to Supabase ->", fname)image.png
            
            # Clean up temp file
            try:
                os.remove(local_path)
            except:
                pass
        except Exception as e:
            print("[ingest] Supabase upload failed, falling back to local:", e)
            # Fallback to local
            path = os.path.join(RAW, fname)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print("[ingest] saved locally ->", path)
    else:
        # Save locally
        path = os.path.join(RAW, f"{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("[ingest] saved ->", path)

def fetch_rss(url, name):
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/rss+xml, application/xml, text/xml, */*"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print("[ingest] error fetching", url, ":", e)
        return []
    soup = BeautifulSoup(r.content, "xml")
    items = []
    for item in soup.find_all("item")[:10]:
        items.append({
            "title": item.title.text if item.title else "",
            "description": item.description.text if item.description else "",
            "link": item.link.text if item.link else "",
            "pubDate": item.pubDate.text if item.pubDate else "",
            "fetched_at": datetime.utcnow().isoformat(),
            "source": url
        })
    save_json(name, items)
    return items

if __name__ == "__main__":
    feeds = [("https://threatpost.com/feed/","threatpost")]
    for url,name in feeds:
        items = fetch_rss(url, name)
        print(f"[ingest] {name}: {len(items)} items")

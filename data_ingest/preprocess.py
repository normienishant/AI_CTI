import json, re, os, tempfile
from pathlib import Path

# Supabase client (optional)
try:
    from supabase import create_client
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "raw-feeds")
    USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)
    if USE_SUPABASE:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("[preprocess] Using Supabase storage")
    else:
        print("[preprocess] Supabase not configured, using local storage")
        supabase = None
except Exception as e:
    print("[preprocess] Supabase not available:", e)
    USE_SUPABASE = False
    supabase = None

RAW = Path(__file__).parent / "raw"
PROC = Path(__file__).parent / "processed"
PROC.mkdir(exist_ok=True, parents=True)

def clean(t):
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"<.*?>", " ", t)
    return " ".join(t.split())

def get_files_from_supabase():
    """Fetch file list from Supabase bucket"""
    if not USE_SUPABASE or not supabase:
        return []
    try:
        files = supabase.storage.from_(SUPABASE_BUCKET).list()
        # Filter JSON files
        json_files = [f for f in files if f.get('name', '').endswith('.json')]
        return json_files
    except Exception as e:
        print("[preprocess] Error listing Supabase files:", e)
        return []

def load_file_from_supabase(filename):
    """Download and load a file from Supabase"""
    if not USE_SUPABASE or not supabase:
        return None
    try:
        # Download to temp file
        tmp = tempfile.gettempdir()
        local_path = os.path.join(tmp, filename)
        
        # Download from Supabase
        res = supabase.storage.from_(SUPABASE_BUCKET).download(filename)
        with open(local_path, "wb") as f:
            f.write(res)
        
        # Load JSON
        with open(local_path, encoding="utf-8-sig") as f:
            data = json.load(f)
        
        # Clean up temp file
        try:
            os.remove(local_path)
        except:
            pass
        
        return data
    except Exception as e:
        print(f"[preprocess] Error loading {filename} from Supabase:", e)
        return None

def run():
    total = 0
    
    if USE_SUPABASE and supabase:
        # Read from Supabase
        supabase_files = get_files_from_supabase()
        if not supabase_files:
            print("[preprocess] no files found in Supabase bucket.")
            return
        
        for file_info in supabase_files:
            filename = file_info.get('name', '')
            if not filename.endswith('.json'):
                continue
            
            print(f"[preprocess] processing from Supabase: {filename}")
            data = load_file_from_supabase(filename)
            if not data:
                continue
            
            if not isinstance(data, list):
                data = [data]
            
            stem = Path(filename).stem
            for i, it in enumerate(data):
                text = clean((it.get("title","") + " " + it.get("description","")).strip())
                out = {
                    "text": text, 
                    "link": it.get("link",""),
                    "title": it.get("title",""),
                    "source": it.get("source","")
                }
                proc_filename = f"{stem}_{i}.json"
                with open(PROC / proc_filename, "w", encoding="utf-8") as o:
                    json.dump(out, o, indent=2, ensure_ascii=False)
                total += 1
            print(f"[preprocess] processed: {filename} -> {len(data)} items")
    else:
        # Fallback to local files
        files = list(RAW.glob("*.json"))
        if not files:
            print("[preprocess] no raw files found.")
            return
        
        for f in files:
            try:
                data = json.load(open(f, encoding="utf-8-sig"))
            except Exception as e:
                print("[preprocess] error reading", f.name, ":", e)
                continue
            if not data:
                print("[preprocess] empty:", f.name)
                continue
            if not isinstance(data, list):
                data = [data]
            
            for i, it in enumerate(data):
                text = clean((it.get("title","") + " " + it.get("description","")).strip())
                out = {
                    "text": text, 
                    "link": it.get("link",""),
                    "title": it.get("title",""),
                    "source": it.get("source","")
                }
                with open(PROC / f"{f.stem}_{i}.json", "w", encoding="utf-8") as o:
                    json.dump(out, o, indent=2, ensure_ascii=False)
                total += 1
            print("[preprocess] processed:", f.name)
    
    print("[preprocess] total processed ->", total)

if __name__ == "__main__":
    run()


# data_ingest/live_ingest.py
import feedparser, json, re
from datetime import datetime
from pathlib import Path

OUT = Path(__file__).resolve().parent / "raw"
OUT.mkdir(parents=True, exist_ok=True)

# Real threat feeds
FEEDS = [
    "https://threatpost.com/feed/",
    "https://www.bleepingcomputer.com/feed/",
    "https://feeds.feedburner.com/TheHackersNews",
]

def clean_text(t):
    return re.sub(r"\s+", " ", t.replace("\n", " ")).strip()

def fetch_live_feeds():
    articles = []
    for url in FEEDS:
        print(f"[feed] fetching: {url}")
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]:
            articles.append({
                "title": clean_text(entry.title),
                "description": clean_text(entry.get("summary", "")),
                "link": entry.link,
                "source": url,
                "fetched_at": datetime.now().isoformat()
            })
    out_file = OUT / f"live_feed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)
    print(f"[feed] saved -> {out_file}")
    return out_file

if __name__ == "__main__":
    fetch_live_feeds()

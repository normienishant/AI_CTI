import json
from pathlib import Path
import numpy as np
import sys, os
os.sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from sklearn.cluster import KMeans
from utils.embeddings import embed_texts


PROC = Path(__file__).resolve().parent.parent / "data_ingest" / "processed"
OUT = Path(__file__).resolve().parent.parent / "data_results"
OUT.mkdir(parents=True, exist_ok=True)

def run(n_clusters=3):
    files = list(PROC.glob("*.json"))
    if not files:
        print("[cluster] no processed files found")
        return
    texts, fnames = [], []
    for f in files:
        with f.open(encoding="utf-8") as fh:
            d = json.load(fh)
        text = d.get("text", "").strip()
        if not text:
            continue
        texts.append(text)
        fnames.append(f.name)
    print(f"[cluster] embedding {len(texts)} docs...")
    emb = embed_texts(texts)
    k = min(n_clusters, len(texts))
    km = KMeans(n_clusters=k, random_state=42)
    labels = km.fit_predict(emb)
    clusters = {}
    for name, label in zip(fnames, labels):
        clusters.setdefault(int(label), []).append(name)
    out = {"n_docs": len(texts), "clusters": clusters}
    with open(OUT / "clusters.json", "w", encoding="utf-8") as fo:
        json.dump(out, fo, indent=2, ensure_ascii=False)
    print(f"[cluster] saved -> {OUT / 'clusters.json'} with {len(clusters)} clusters")

if __name__ == "__main__":
    run()


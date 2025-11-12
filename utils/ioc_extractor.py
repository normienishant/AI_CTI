import re, json
from pathlib import Path

PROC = Path(__file__).resolve().parent.parent / "data_ingest" / "processed"
OUT = Path(__file__).resolve().parent.parent / "data_results"
OUT.mkdir(parents=True, exist_ok=True)

ipv4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
domain = re.compile(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b")
cve = re.compile(r"CVE-\d{4}-\d{4,7}", re.I)

def run():
    results = []
    for f in PROC.glob("*.json"):
        try:
            doc = json.load(open(f, encoding="utf-8"))
        except Exception as e:
            print("[ioc] error reading", f.name, ":", e)
            continue
        text = doc.get("text","") + " " + doc.get("link","")
        iocs = {
            "ips": list(set(ipv4.findall(text))),
            "domains": list(set(domain.findall(text))),
            "cves": list(set([x.upper() for x in cve.findall(text)]))
        }
        results.append({
            "file": f.name, 
            "iocs": iocs,
            "link": doc.get("link", ""),
            "title": doc.get("title", ""),
            "source": doc.get("source", "")
        })
    outp = OUT / "iocs_results.json"
    with open(outp, "w", encoding="utf-8") as fo:
        json.dump(results, fo, indent=2, ensure_ascii=False)
    print("[ioc] saved ->", outp, "docs:", len(results))

if __name__ == "__main__":
    run()

# dashboard/app.py - improved (charts + summary)
import streamlit as st, json, pathlib, pandas as pd
from collections import Counter

st.set_page_config(page_title="AI-CTI Dashboard", layout="wide")
ROOT = pathlib.Path(__file__).resolve().parents[1]
RES = ROOT / "data_results"

st.title("AI-CTI Dashboard")

if not RES.exists():
    st.warning("No results yet. Run the pipeline (ingest → preprocess → extract_iocs → analyze).")
else:
    # Load IOCs
    iocs = []
    if (RES / "iocs_results.json").exists():
        iocs = json.loads((RES / "iocs_results.json").read_text(encoding="utf-8"))

    # Load clusters
    clusters = {}
    if (RES / "clusters.json").exists():
        clusters = json.loads((RES / "clusters.json").read_text(encoding="utf-8"))

    # Quick summary row
    c1, c2, c3 = st.columns([1,1,2])
    c1.metric("Processed docs (IOC)", len(iocs))
    c2.metric("Clusters detected", len(clusters.get("clusters", {})))
    c3.write("")  # placeholder

    # Build IOCs summary table
    rows = []
    for doc in iocs:
        fname = doc.get("file")
        i = doc.get("iocs", {})
        ips = i.get("ips", [])
        domains = i.get("domains", [])
        cves = i.get("cves", [])
        rows.append({
            "file": fname,
            "n_ips": len(ips),
            "n_domains": len(domains),
            "n_cves": len(cves),
            "total": len(ips) + len(domains) + len(cves),
            "ips": ", ".join(ips) if ips else "",
            "domains": ", ".join(domains) if domains else "",
            "cves": ", ".join(cves) if cves else ""
        })

    if rows:
        df = pd.DataFrame(rows).sort_values("total", ascending=False).reset_index(drop=True)
        st.header("Top IOCs (by total found)")
        st.dataframe(df[["file","n_ips","n_domains","n_cves","total"]].head(20), use_container_width=True)

        # Show details for top row on selection
        sel = st.selectbox("Show details for", options=df["file"].tolist(), index=0)
        detail = df[df["file"]==sel].iloc[0]
        st.subheader(f"Details — {sel}")
        st.markdown(f"- **IPs:** `{detail.ips}`")
        st.markdown(f"- **Domains:** `{detail.domains}`")
        st.markdown(f"- **CVEs:** `{detail.cves}`")
    else:
        st.info("No IOC results found yet.")

    # Cluster size chart
    st.header("Cluster sizes")
    clusters_map = clusters.get("clusters", {}) if isinstance(clusters, dict) else {}
    sizes = {k: len(v) for k,v in clusters_map.items()}
    if sizes:
        s = pd.Series(sizes).sort_values(ascending=False)
        st.bar_chart(s)
    else:
        st.info("No clusters found yet.")

    # Expandable cluster lists
    st.header("Clusters (detailed)")
    if clusters_map:
        for k, files in sorted(clusters_map.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else x[0]):
            with st.expander(f"Cluster {k} — {len(files)} docs"):
                for fn in files:
                    # show link to processed file if present
                    proc_file = (ROOT / "data_ingest" / "processed" / fn)
                    if proc_file.exists():
                        st.markdown(f"- `{fn}` — [open file](file:///{proc_file.resolve()})")
                    else:
                        st.markdown(f"- `{fn}`")
    else:
        st.write("No cluster details available.")

    # raw JSON peek (collapsible)
    if st.checkbox("Show raw results JSON (iocs + clusters)"):
        st.subheader("iocs_results.json")
        st.code(json.dumps(iocs, indent=2, ensure_ascii=False), language="json")
        st.subheader("clusters.json")
        st.code(json.dumps(clusters, indent=2, ensure_ascii=False), language="json")

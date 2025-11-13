#!/usr/bin/env python3
"""Generate a simple ingestion health report for AI-CTI."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


def fetch(path: str) -> Any:
    url = f"{BACKEND_URL}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "AI-CTI-Health-Check/1.0"})
    with urllib.request.urlopen(req, timeout=40) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def build_summary(payload: dict) -> str:
    feeds = payload.get("feeds", []) or []
    iocs = payload.get("iocs", []) or []
    generated = payload.get("generated_at")
    latest = None
    if feeds:
        latest = feeds[0].get("published_at") or feeds[0].get("fetched_at")

    top_sources = {}
    for item in feeds:
        source = item.get("source") or "unknown"
        top_sources[source] = top_sources.get(source, 0) + 1

    top_sources_list = sorted(top_sources.items(), key=lambda kv: kv[1], reverse=True)[:5]
    top_sources_str = "\n".join(f"- {name}: {count}" for name, count in top_sources_list) or "- none"

    lines = [
        "## AI-CTI Ingestion Health",
        f"- Backend: `{BACKEND_URL}`",
        f"- Headlines in latest batch: **{len(feeds)}**",
        f"- IOCs harvested: **{len(iocs)}**",
        f"- Generated at: `{generated or 'n/a'}`",
        f"- Latest headline timestamp: `{latest or 'n/a'}`",
        "",
        "### Top sources",
        top_sources_str,
    ]
    return "\n".join(lines)


def main() -> int:
    try:
        payload = fetch("/results")
    except urllib.error.URLError as exc:  # pragma: no cover - runtime
        print(f"::error::Failed to fetch /results from {BACKEND_URL}: {exc}")
        return 1

    summary = build_summary(payload)
    print(summary)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write(summary)
            handle.write("\n")

    log_path = os.environ.get("GITHUB_WORKSPACE")
    if log_path:
        with open(os.path.join(log_path, "health_report.log"), "w", encoding="utf-8") as handle:
            handle.write(summary)

    timestamp = datetime.utcnow().isoformat()
    print(f"Report generated at {timestamp} UTC")
    return 0


if __name__ == "__main__":
    sys.exit(main())

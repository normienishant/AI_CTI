## AI-CTI — Cyber Threat Intelligence Desk

AI-CTI is a full-stack threat-intelligence dashboard that aggregates live cybersecurity news, extracts high-signal indicators, and presents them in a newsroom-grade interface.

### Features

- **Live feeds**: pulls from ThreatPost, BleepingComputer, DarkReading, CSO Online, and The Hacker News.
- **Enriched metadata**: resolves OG/Twitter preview images and stores them in Supabase Storage.
- **IOC harvesting**: extracts IPs, domains, and CVEs per batch and persists them to Supabase.
- **Professional UI**: responsive dashboard with auto-refreshing ticker, article imagery, and analyst sidebar.
- **Automation ready**: GitHub Action and optional backend scheduler for 30-minute refresh cadence.

### Repository layout

| Path | Description |
| --- | --- |
| `api/` | FastAPI service that exposes fetch endpoints and proxies data from Supabase. |
| `data_ingest/` | Feed ingestion, preprocessing, and IOC extraction scripts. |
| `aicti-frontend/` | Next.js + Tailwind frontend. |
| `docs/` | Environment templates and Supabase schema helpers. |
| `.github/workflows/fetch-live.yml` | Scheduled workflow that triggers live ingestion. |

### Quick start

1. **Backend**
   ```bash
   cd api_cti
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   cp docs/env.example .env   # fill in Supabase credentials
   uvicorn api.main:app --reload --port 8000
   ```

2. **Frontend**
   ```bash
   cd aicti-frontend
   npm install
   cp docs.env.local.example .env.local
   npm run dev
   ```
   Visit `http://localhost:3000/dashboard`.

3. **Live ingestion**
   ```bash
   # requires SUPABASE_* env vars in .env
   python data_ingest/live_ingest_supabase.py
   ```

### Supabase schema

- Storage bucket `raw-feeds` hosts JSON batches and uploaded thumbnails.
- Table definitions live in `docs/supabase_schema.sql` (articles + iocs).

### Automation

- Set `ENABLE_SCHEDULER=true` for in-process cron (every 30 min).
- Configure GitHub secrets `BACKEND_URL` (and optional `BACKEND_TRIGGER_TOKEN`) to activate the bundled workflow.

### Deployment

See [`README_DEPLOY.md`](README_DEPLOY.md) for step-by-step instructions covering Supabase, Render/Railway, and Vercel.


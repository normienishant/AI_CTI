# AI-CTI Operations Playbook

## Saved Briefings

- **Table**: `saved_briefings`
- **Columns**:
  - `client_id` (text) – anonymous browser/device identifier (composite key with `link`)
  - `link` (text, unique per client)
  - `title` (text)
  - `source` (text)
  - `image_url` (text)
  - `risk_level` (text)
  - `risk_score` (numeric)
  - `saved_at` (timestamp, default `now()`)
- **Policy**: allow inserts/updates/deletes for the service role key only. Frontend never touches this table directly; all access flows through the FastAPI backend.

## Supabase Storage

- `raw-feeds` – JSON archives of each ingestion batch (already public).
- `article-thumbnails` – OG/Twitter images for articles. Must remain public so the frontend can render thumbnails. Set a `public-read` policy or mark the bucket as public.

## Ingestion Health Workflow

A scheduled GitHub Action (`.github/workflows/ingestion-health.yml`) runs every 6 hours (and can be triggered manually). It calls `scripts/report_health.py`, which hits the FastAPI `/results` endpoint and writes a summary to the workflow logs and job summary.

### Setup

1. In the repository secrets, add `BACKEND_URL` pointing to the Render FastAPI deployment (e.g., `https://ai-cti-api.onrender.com`).
2. The workflow runs with system Python (no dependencies required).
3. The generated summary appears under the workflow run’s “Summary” tab and inside `health_report.log` artifact for quick auditing.

## Manual Checks

- **Refresh ingestion**: `POST /fetch_live` (available through Render interface or the frontend “Fetch Latest Batch” button).
- **Verify Supabase quotas**: run the cleanup task automatically invoked by `/fetch_live`; it keeps 200 recent articles and prunes anything older than 7 days.
- **Saved briefing audit**: query `saved_briefings` in Supabase to ensure counts stay reasonable, or clear old entries by `saved_at`.

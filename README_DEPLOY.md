# AI-CTI Deployment Guide

This guide covers how to deploy the AI-CTI (AI-based Cyber Threat Intelligence) platform to production.

## 📋 Prerequisites

- GitHub account
- Supabase account (for storage and database)
- Vercel account (for frontend hosting)
- Railway or Render account (for backend hosting)

## 🗄️ Supabase Setup

1. Create a new Supabase project at https://supabase.com
2. Create a storage bucket named `raw-feeds`:
   - Go to Storage → Create Bucket
   - Name: `raw-feeds`
   - Make it public or configure RLS policies as needed
3. Create an `articles` and `iocs` table (execute via SQL editor):
   ```sql
   CREATE TABLE IF NOT EXISTS public.articles (
     id BIGSERIAL PRIMARY KEY,
     title TEXT,
     description TEXT,
     link TEXT UNIQUE,
     source TEXT,
     source_name TEXT,
     image_url TEXT,
     published_at TIMESTAMPTZ,
     fetched_at TIMESTAMPTZ DEFAULT timezone('utc', now())
   );

   CREATE INDEX IF NOT EXISTS idx_articles_published_at
     ON public.articles (published_at DESC NULLS LAST);

   CREATE TABLE IF NOT EXISTS public.iocs (
     id BIGSERIAL PRIMARY KEY,
     file TEXT,
     type TEXT,
     value TEXT,
     created_at TIMESTAMPTZ DEFAULT timezone('utc', now())
   );

   CREATE INDEX IF NOT EXISTS idx_iocs_type ON public.iocs (type);
   ```
4. (Optional) Create a dedicated storage bucket for article thumbnails (e.g. `raw-feeds`) and mark it public or add signed URL policies.
5. Get your Supabase credentials:
   - Project URL: `https://your-project.supabase.co`
   - Service Role Key (Settings → API) – required for server-side ingestion

## 🚀 Backend Deployment (Railway or Render)

### Option 1: Railway

1. **Create a new project:**
   - Go to https://railway.app
   - Click "New Project" → "Deploy from GitHub repo"
   - Select your repository

2. **Configure environment variables:**
   - Go to Variables tab
   - Add the following:
     ```
     SUPABASE_URL=https://your-project.supabase.co
     SUPABASE_KEY=your-supabase-service-role-key
     SUPABASE_SERVICE_KEY=your-supabase-service-role-key
     SUPABASE_BUCKET=raw-feeds
     ENABLE_SCHEDULER=false
     PORT=8000
     ```

3. **Deploy:**
   - Railway will automatically detect the `Procfile` or `Dockerfile`
   - The app will start on the provided URL

4. **Get your backend URL:**
   - Copy the public URL (e.g., `https://your-app.railway.app`)

### Option 2: Render

1. **Create a new Web Service:**
   - Go to https://render.com
   - Click "New" → "Web Service"
   - Connect your GitHub repository

2. **Configure settings:**
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python -m uvicorn api.main:app --host 0.0.0.0 --port $PORT`
   - **Environment:** Python 3

3. **Add environment variables:**
   - Go to Environment tab
   - Add the same variables as Railway (see above)

4. **Deploy:**
   - Click "Create Web Service"
   - Render will build and deploy automatically

## 🎨 Frontend Deployment (Vercel)

1. **Import project:**
   - Go to https://vercel.com
   - Click "Add New" → "Project"
   - Import your GitHub repository

2. **Configure project:**
   - **Root Directory:** `aicti-frontend`
   - **Framework Preset:** Next.js
   - **Build Command:** `npm run build` (auto-detected)
   - **Output Directory:** `.next` (auto-detected)

3. **Add environment variable:**
   - Go to Settings → Environment Variables
   - Add:
     ```
     NEXT_PUBLIC_API_URL=https://your-backend-url.railway.app
     ```
   - Replace with your actual backend URL

4. **Deploy:**
   - Click "Deploy"
   - Vercel will build and deploy automatically
   - Your frontend will be available at `https://your-app.vercel.app`

## ⚙️ Local Development

### Backend

1. **Set up virtual environment:**
   ```powershell
   cd C:\Users\nisha\OneDrive\Desktop\ai_cti\ai_cti
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Create `.env` file:**
   - Copy the template at `docs/env.example` to `.env` and edit with Supabase credentials.

4. **Run the backend:**
   ```powershell
   python -m uvicorn api.main:app --reload --port 8000
   ```
   - API will be available at http://127.0.0.1:8000
   - API docs at http://127.0.0.1:8000/docs

### Frontend

1. **Navigate to frontend directory:**
   ```powershell
   cd aicti-frontend
   ```

2. **Install dependencies:**
   ```powershell
   npm install
   ```

3. **Create `.env.local` file:**
   - Copy `docs.env.local.example` to `.env.local` and set:
     ```
     NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
     ```

4. **Run the frontend:**
   ```powershell
   npm run dev
   ```
   - Dashboard will be available at http://localhost:3000/dashboard

## 🔄 Automatic Feed Updates

### Option 1: Built-in Scheduler (Backend)

Enable the built-in scheduler by setting:
```
ENABLE_SCHEDULER=true
```

This will automatically fetch feeds every 30 minutes as long as your backend process remains online.

### Option 2: GitHub Actions (Recommended for Production)

This repository ships with `.github/workflows/fetch-live.yml` which triggers the backend every 30 minutes.

1. **Add secrets in GitHub:**
   - `BACKEND_URL` – e.g. `https://your-backend-url.railway.app`
   - (Optional) `BACKEND_TRIGGER_TOKEN` if your backend requires auth
2. **Enable the workflow** (defaults to scheduled + manual dispatch).
3. The action will POST to `/fetch_live`, ensuring fresh data without keeping the backend awake.

## 📝 API Endpoints

- `GET /results` - Get IOC and cluster results
- `POST /fetch_live` - Fetch live feeds from RSS sources
- `POST /ingest` - Run ingestion (legacy)
- `POST /preprocess` - Preprocess raw feeds
- `POST /extract_iocs` - Extract IOCs from processed feeds
- `POST /analyze` - Run clustering analysis
- `POST /run_all` - Run full pipeline synchronously

## 🔍 Verification

After deployment, verify:

1. **Backend is running:**
   - Visit `https://your-backend-url/docs` - should show FastAPI docs
   - Visit `https://your-backend-url/results` - should return JSON

2. **Frontend is connected:**
   - Visit `https://your-frontend-url/dashboard`
   - Click "Refresh Data" - should load data from backend

3. **Feed ingestion works:**
   - POST to `https://your-backend-url/fetch_live`
   - Check Supabase bucket - should see new JSON files

## 🐛 Troubleshooting

### Backend Issues

- **Port binding errors:** Ensure `PORT` env var is set (Railway/Render set this automatically)
- **Supabase connection errors:** Verify `SUPABASE_URL` and `SUPABASE_KEY` are correct
- **Import errors:** Ensure all dependencies are in `requirements.txt`

### Frontend Issues

- **CORS errors:** Backend CORS is set to allow all origins (`*`)
- **API connection errors:** Verify `BACKEND_URL` env var is set correctly
- **Build errors:** Run `npm run build` locally to check for issues

### Supabase Issues

- **Bucket not found:** Ensure bucket `raw-feeds` exists and is accessible
- **Permission errors:** Check RLS policies or make bucket public for testing

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
- [Supabase Documentation](https://supabase.com/docs)
- [Vercel Documentation](https://vercel.com/docs)
- [Railway Documentation](https://docs.railway.app/)
- [Render Documentation](https://render.com/docs)

## 🔐 Security Notes

- Never commit `.env` files to git
- Use environment variables for all secrets
- Consider using Supabase RLS (Row Level Security) for production
- Limit CORS origins in production (currently set to `*` for development)


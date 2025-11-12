# 🚀 AI-CTI Hosting Guide - Step by Step

## ✅ Step 1: Supabase Setup (Database + Storage)

### 1.1 Create Supabase Project
1. Go to https://supabase.com
2. Sign up / Login
3. Click **"New Project"**
4. Fill:
   - **Name**: `ai-cti` (or any name)
   - **Database Password**: Strong password (save it!)
   - **Region**: Choose closest to you
5. Wait 2-3 minutes for project to create

### 1.2 Create Storage Bucket
1. In Supabase dashboard → **Storage** (left sidebar)
2. Click **"New bucket"**
3. Name: `raw-feeds`
4. **Public bucket**: ✅ Check this (so images can be accessed)
5. Click **"Create bucket"**

### 1.3 Create Database Tables
1. Go to **SQL Editor** (left sidebar)
2. Click **"New query"**
3. Copy-paste this entire SQL:

```sql
-- Create articles table
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

-- Create IOCs table
CREATE TABLE IF NOT EXISTS public.iocs (
  id BIGSERIAL PRIMARY KEY,
  file TEXT,
  type TEXT,
  value TEXT,
  created_at TIMESTAMPTZ DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_iocs_type ON public.iocs (type);
```

4. Click **"Run"** (or press Ctrl+Enter)
5. Should see "Success. No rows returned"

### 1.4 Get Supabase Credentials
1. Go to **Settings** → **API** (left sidebar)
2. Copy these 2 values:
   - **Project URL**: `https://xxxxx.supabase.co` (copy this)
   - **service_role key**: Click "Reveal" and copy the long key (starts with `eyJ...`)

**Save both in a text file - you'll need them!**

---

## ✅ Step 2: Backend Deployment (Render or Railway)

### Option A: Render (Recommended - Free tier available)

1. Go to https://render.com → Sign up/Login
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repo:
   - Click **"Connect GitHub"**
   - Authorize Render
   - Select your `ai_cti` repository
4. Fill deployment settings:
   - **Name**: `ai-cti-backend`
   - **Region**: Choose closest
   - **Branch**: `main` (or your main branch)
   - **Root Directory**: Leave empty (or `ai_cti` if repo is nested)
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python -m uvicorn api.main:app --host 0.0.0.0 --port $PORT`
5. **Environment Variables** (click "Add Environment Variable" for each):
   ```
   SUPABASE_URL=https://xxxxx.supabase.co
   SUPABASE_SERVICE_KEY=eyJ... (your service role key)
   SUPABASE_KEY=eyJ... (same as above)
   SUPABASE_BUCKET=raw-feeds
   SUPABASE_IMAGE_BUCKET=raw-feeds
   DEFAULT_ARTICLE_IMAGE=https://placehold.co/600x360/0f172a/ffffff?text=AI-CTI
   ENABLE_SCHEDULER=false
   ```
6. Click **"Create Web Service"**
7. Wait 5-10 minutes for first deploy
8. Copy your backend URL: `https://ai-cti-backend.onrender.com` (or similar)

**Test**: Open `https://your-backend-url.onrender.com/docs` - should see FastAPI docs!

### Option B: Railway (Alternative)

1. Go to https://railway.app → Sign up/Login
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your `ai_cti` repo
4. Railway auto-detects Python
5. Add Environment Variables (same as Render above)
6. Deploy → Copy URL: `https://xxxxx.up.railway.app`

---

## ✅ Step 3: Frontend Deployment (Vercel)

1. Go to https://vercel.com → Sign up/Login (use GitHub)
2. Click **"Add New..."** → **"Project"**
3. Import your GitHub repo
4. **Project Settings**:
   - **Framework Preset**: Next.js (auto-detected)
   - **Root Directory**: `ai_cti/aicti-frontend` (or just `aicti-frontend` if repo root)
   - **Build Command**: `npm run build` (auto)
   - **Output Directory**: `.next` (auto)
5. **Environment Variables**:
   - Click **"Add"**
   - Name: `NEXT_PUBLIC_API_URL`
   - Value: `https://your-backend-url.onrender.com` (from Step 2, NO trailing slash)
6. Click **"Deploy"**
7. Wait 2-3 minutes
8. Copy your frontend URL: `https://ai-cti.vercel.app` (or similar)

**Test**: Open the Vercel URL → Should see your dashboard!

---

## ✅ Step 4: GitHub Action Setup (Auto-refresh every 30 min)

1. Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **"New repository secret"**
3. Add these secrets:

   **Secret 1:**
   - Name: `BACKEND_URL`
   - Value: `https://your-backend-url.onrender.com` (from Step 2, NO trailing slash)

   **Secret 2 (Optional - for future auth):**
   - Name: `BACKEND_TRIGGER_TOKEN`
   - Value: Leave empty for now (or any random string if you add auth later)

4. Go to **Actions** tab in your repo
5. You should see **"Fetch Live Feeds"** workflow
6. Click it → **"Run workflow"** → **"Run workflow"** (manual test)
7. Check logs - should show "Triggering https://..."

**Now it will auto-run every 30 minutes!**

---

## ✅ Step 5: First Data Fetch (Manual Trigger)

### Option A: Via GitHub Action
1. Go to **Actions** tab
2. Click **"Fetch Live Feeds"**
3. Click **"Run workflow"** → **"Run workflow"**
4. Wait 30 seconds, check logs

### Option B: Via Backend API
1. Open: `https://your-backend-url.onrender.com/docs`
2. Find **POST /fetch_live**
3. Click **"Try it out"** → **"Execute"**
4. Should return: `{"status": "live feed ingestion started"}`

### Option C: Via Frontend
1. Open your Vercel frontend URL
2. Click **"Fetch Latest Batch"** button
3. Wait 1-2 minutes
4. Refresh page - should see real articles!

---

## ✅ Step 6: Verify Everything Works

### Check Supabase:
1. Go to Supabase → **Table Editor** → `articles`
2. Should see rows with titles, links, images
3. Go to **Storage** → `raw-feeds` → Should see JSON files + images

### Check Backend:
1. Open: `https://your-backend-url.onrender.com/results`
2. Should see JSON with `feeds`, `iocs` arrays

### Check Frontend:
1. Open your Vercel URL
2. Should see:
   - Real article cards with thumbnails
   - Ticker scrolling
   - Sidebar with trending topics
   - Stats showing IOC counts

---

## 🐛 Troubleshooting

### Backend not working?
- Check Render/Railway logs
- Verify all env vars are set correctly
- Check Supabase URL/key are correct

### Frontend shows no data?
- Check browser console (F12) for errors
- Verify `NEXT_PUBLIC_API_URL` is correct in Vercel
- Test backend `/results` endpoint directly

### GitHub Action failing?
- Check `BACKEND_URL` secret is set correctly
- Verify backend is accessible (no auth required)
- Check Action logs for error messages

### No images showing?
- Verify Supabase bucket `raw-feeds` is **public**
- Check Storage → Policies → Make bucket public
- Or add RLS policy to allow public read

---

## 🎉 Done!

Your AI-CTI dashboard is now live and auto-updating every 30 minutes!

**Your URLs:**
- Frontend: `https://ai-cti.vercel.app`
- Backend: `https://ai-cti-backend.onrender.com`
- Supabase: `https://xxxxx.supabase.co`

Bookmark them and share! 🚀


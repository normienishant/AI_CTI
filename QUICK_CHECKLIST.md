# ✅ AI-CTI Deployment Quick Checklist

## Before You Start
- [ ] GitHub repo is pushed and public/accessible
- [ ] You have accounts ready:
  - [ ] Supabase (free tier OK)
  - [ ] Render/Railway (free tier OK)
  - [ ] Vercel (free tier OK)

---

## Step 1: Supabase (10 minutes)
- [ ] Created project at supabase.com
- [ ] Created storage bucket `raw-feeds` (public)
- [ ] Ran SQL script to create `articles` and `iocs` tables
- [ ] Copied Project URL
- [ ] Copied Service Role Key (from Settings → API)

---

## Step 2: Backend Deploy (15 minutes)
- [ ] Created Render/Railway account
- [ ] Connected GitHub repo
- [ ] Set build command: `pip install -r requirements.txt`
- [ ] Set start command: `python -m uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- [ ] Added all 7 environment variables:
  - [ ] `SUPABASE_URL`
  - [ ] `SUPABASE_SERVICE_KEY`
  - [ ] `SUPABASE_KEY`
  - [ ] `SUPABASE_BUCKET=raw-feeds`
  - [ ] `SUPABASE_IMAGE_BUCKET=raw-feeds`
  - [ ] `DEFAULT_ARTICLE_IMAGE=...`
  - [ ] `ENABLE_SCHEDULER=false`
- [ ] Deployed successfully
- [ ] Tested: `https://your-backend.onrender.com/docs` works
- [ ] **Saved backend URL** ✅

---

## Step 3: Frontend Deploy (10 minutes)
- [ ] Created Vercel account (GitHub login)
- [ ] Imported repo
- [ ] Set root directory: `ai_cti/aicti-frontend` (or `aicti-frontend`)
- [ ] Added env var: `NEXT_PUBLIC_API_URL=https://your-backend.onrender.com`
- [ ] Deployed successfully
- [ ] Tested: Frontend URL loads
- [ ] **Saved frontend URL** ✅

---

## Step 4: GitHub Action (5 minutes)
- [ ] Went to repo → Settings → Secrets
- [ ] Added secret: `BACKEND_URL` = your backend URL
- [ ] Tested workflow: Actions → "Fetch Live Feeds" → Run workflow
- [ ] Checked logs - no errors

---

## Step 5: First Data Fetch (2 minutes)
- [ ] Triggered `/fetch_live` (via GitHub Action OR backend docs OR frontend button)
- [ ] Waited 1-2 minutes
- [ ] Checked Supabase → `articles` table has rows
- [ ] Checked frontend shows real articles with images

---

## Step 6: Final Verification
- [ ] Frontend shows article cards ✅
- [ ] Images load correctly ✅
- [ ] Ticker scrolls ✅
- [ ] Sidebar shows trending topics ✅
- [ ] Stats show IOC counts ✅
- [ ] "Fetch Latest" button works ✅

---

## 🎉 All Done!
Your project is live and auto-updating every 30 minutes!

**Need help?** Check `HOSTING_STEPS.md` for detailed instructions.


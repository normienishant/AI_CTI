# 🔄 Automatic Fetching Setup

## Current Status

Your AI-CTI project supports **automatic fetching** in two ways:

### ✅ Option 1: GitHub Actions (Recommended - Already Set Up)

**Status:** ✅ Ready to use (needs GitHub secret)

**How it works:**
- GitHub Action runs every 30 minutes automatically
- Triggers your backend `/fetch_live` endpoint
- Fetches latest news from RSS feeds
- Uploads to Supabase

**Setup:**
1. Go to GitHub repo → Settings → Secrets and variables → Actions
2. Add secret: `BACKEND_URL` = `https://ai-cti-1-8c7w.onrender.com`
3. (Optional) Add secret: `BACKEND_TRIGGER_TOKEN` if you add auth later
4. Done! Action will run automatically every 30 minutes

**Check status:**
- GitHub repo → Actions tab
- You'll see "Fetch Live Feeds" workflow running every 30 minutes

---

### ✅ Option 2: Backend Scheduler (Alternative)

**Status:** ⚠️ Requires always-on instance (not free tier)

**How it works:**
- Backend runs a scheduler that triggers `/fetch_live` every 30 minutes
- Only works if your Render instance is always-on (paid plan)

**Setup:**
1. Render dashboard → Environment Variables
2. Add: `ENABLE_SCHEDULER=true`
3. Redeploy
4. Done! Backend will fetch automatically

**Note:** Free tier instances spin down after inactivity, so scheduler won't work on free tier.

---

## Manual Fetching

You can always trigger a fetch manually:

1. **Via Frontend:**
   - Click "Fetch Latest Batch" button on dashboard

2. **Via Backend API:**
   ```
   POST https://ai-cti-1-8c7w.onrender.com/fetch_live
   ```

3. **Via GitHub Actions:**
   - Go to Actions tab → "Fetch Live Feeds" → "Run workflow"

---

## Recommendation

**Use GitHub Actions (Option 1)** because:
- ✅ Works with free tier
- ✅ Reliable and independent of backend status
- ✅ Already configured in your repo
- ✅ Can see logs and history

Just add the `BACKEND_URL` secret and you're done!


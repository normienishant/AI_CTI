# AI-CTI Deployment Checklist

Use this checklist to verify your deployment is working correctly.

## ✅ Pre-Deployment

- [ ] Supabase project created
- [ ] `raw-feeds` bucket created in Supabase
- [ ] `iocs` table created (optional)
- [ ] Supabase credentials saved securely
- [ ] GitHub repository is up to date
- [ ] `.env.sample` file exists
- [ ] `.gitignore` includes `.env`

## ✅ Backend Deployment

- [ ] Backend deployed to Railway/Render
- [ ] Environment variables configured:
  - [ ] `SUPABASE_URL`
  - [ ] `SUPABASE_KEY`
  - [ ] `SUPABASE_BUCKET`
  - [ ] `ENABLE_SCHEDULER` (optional)
- [ ] Backend URL accessible (test `/docs` endpoint)
- [ ] `/results` endpoint returns data (may be empty initially)
- [ ] Backend logs show no errors

## ✅ Frontend Deployment

- [ ] Frontend deployed to Vercel
- [ ] `BACKEND_URL` environment variable set
- [ ] Frontend URL accessible
- [ ] Dashboard page loads (`/dashboard`)
- [ ] No console errors in browser
- [ ] "Refresh Data" button works

## ✅ Functionality Tests

### Feed Ingestion
- [ ] `POST /fetch_live` endpoint works
- [ ] New files appear in Supabase `raw-feeds` bucket
- [ ] No local temp files left behind
- [ ] IOCs are extracted and stored

### Data Processing
- [ ] `POST /preprocess` processes feeds from Supabase
- [ ] `POST /extract_iocs` extracts IOCs correctly
- [ ] `POST /analyze` creates clusters
- [ ] `POST /run_all` runs full pipeline successfully

### Dashboard Display
- [ ] Metrics cards show correct values:
  - [ ] Processed Docs count
  - [ ] Clusters Detected count
  - [ ] Total IOCs count
- [ ] Cluster size chart displays correctly
- [ ] Top IOCs table shows data
- [ ] Latest feeds list displays:
  - [ ] Feed titles
  - [ ] Source information
  - [ ] Clickable links
- [ ] Feed previews load (OG tags)
- [ ] Cluster details section is collapsible

## ✅ Automatic Updates

### Option 1: Built-in Scheduler
- [ ] `ENABLE_SCHEDULER=true` set
- [ ] Backend logs show scheduled runs
- [ ] Feeds update every 30 minutes

### Option 2: GitHub Actions
- [ ] `.github/workflows/cron-ingest.yml` created
- [ ] `BACKEND_URL` secret added to GitHub
- [ ] Workflow runs successfully
- [ ] Feeds update on schedule

## ✅ Local Development

### Backend
- [ ] Virtual environment created
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file created from `.env.sample`
- [ ] Backend runs locally (`uvicorn api.main:app --reload`)
- [ ] API docs accessible at `http://127.0.0.1:8000/docs`

### Frontend
- [ ] Node modules installed (`npm install`)
- [ ] `.env.local` created with `BACKEND_URL`
- [ ] Frontend runs locally (`npm run dev`)
- [ ] Dashboard accessible at `http://localhost:3000/dashboard`
- [ ] Frontend connects to local backend

## ✅ Production Verification

- [ ] Frontend deployed and accessible
- [ ] Backend deployed and accessible
- [ ] Frontend can communicate with backend
- [ ] Feed ingestion works in production
- [ ] Dashboard displays real data
- [ ] All links and buttons functional
- [ ] No errors in browser console
- [ ] No errors in backend logs

## 🐛 Common Issues

If something doesn't work, check:

- [ ] Environment variables are set correctly
- [ ] Supabase bucket exists and is accessible
- [ ] CORS is configured (backend allows frontend origin)
- [ ] Backend URL is correct in frontend env vars
- [ ] Port is set correctly (Railway/Render auto-sets `PORT`)
- [ ] Dependencies are installed (check `requirements.txt`)
- [ ] Build succeeds locally before deploying

## 📊 Performance Checks

- [ ] Dashboard loads in < 3 seconds
- [ ] API responses are < 1 second
- [ ] Feed ingestion completes in < 30 seconds
- [ ] No memory leaks (check backend logs)
- [ ] Supabase storage usage is reasonable

## 🔒 Security Checks

- [ ] No secrets in code or logs
- [ ] `.env` files are in `.gitignore`
- [ ] Supabase RLS policies configured (if needed)
- [ ] CORS origins limited (if needed)
- [ ] API endpoints secured (if needed)

## 📝 Documentation

- [ ] `README_DEPLOY.md` is up to date
- [ ] `CHECKLIST.md` is complete
- [ ] Code comments are clear
- [ ] Environment variables are documented

---

**Last Updated:** After completing all items, your AI-CTI platform should be fully functional and deployed! 🎉


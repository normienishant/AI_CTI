# 🔧 Troubleshooting Guide

## ❌ "Failed to fetch" Error

### **Problem:**
Frontend shows "Failed to fetch" and no news articles are displayed.

### **Possible Causes & Solutions:**

#### 1. **Backend URL Not Set in Vercel** (Most Common)

**Check:**
- Vercel dashboard → Project → Settings → Environment Variables
- Look for `NEXT_PUBLIC_API_URL`

**Fix:**
1. Go to Vercel dashboard
2. Select your project
3. Settings → Environment Variables
4. Add/Update:
   - **Name:** `NEXT_PUBLIC_API_URL`
   - **Value:** `https://ai-cti-1-8c7w.onrender.com` (your backend URL, NO trailing slash)
5. **Redeploy** (or wait for auto-redeploy)

---

#### 2. **Backend is Spinning Down (Free Tier)**

**Symptom:**
- First request fails
- After 30-60 seconds, it works

**Fix:**
- Wait 30-60 seconds and refresh
- Or upgrade to paid tier for always-on instance

---

#### 3. **Backend is Down**

**Check:**
1. Open backend URL: `https://ai-cti-1-8c7w.onrender.com/docs`
2. If 502/503 error, backend is down

**Fix:**
1. Go to Render dashboard
2. Check service status
3. If failed, check logs
4. Redeploy if needed

---

#### 4. **Supabase Connection Issue**

**Check:**
- Render logs → Look for "Supabase fetch failed" or "Invalid API key"

**Fix:**
1. Render dashboard → Environment Variables
2. Verify:
   - `SUPABASE_URL` is correct
   - `SUPABASE_SERVICE_KEY` is correct (Service Role Key, not anon key)
3. Redeploy backend

---

## 🔍 **Quick Debug Steps**

### Step 1: Check Backend
```
Open: https://ai-cti-1-8c7w.onrender.com/results
```
- If JSON shows, backend is working
- If 502/503, backend is down

### Step 2: Check Frontend API Route
```
Open: https://your-frontend.vercel.app/api/results
```
- Should return JSON
- If error, check Vercel environment variables

### Step 3: Check Browser Console
1. Open frontend
2. Press F12 → Console tab
3. Look for errors
4. Check Network tab → `/api/results` request

### Step 4: Check Vercel Environment Variables
1. Vercel dashboard → Project → Settings → Environment Variables
2. Verify `NEXT_PUBLIC_API_URL` is set
3. Value should be: `https://ai-cti-1-8c7w.onrender.com` (NO trailing slash)

---

## ✅ **Quick Fix Checklist**

- [ ] `NEXT_PUBLIC_API_URL` set in Vercel?
- [ ] Backend URL accessible? (test `/docs` endpoint)
- [ ] Backend logs showing errors?
- [ ] Supabase credentials correct in Render?
- [ ] Wait 30-60 seconds (free tier spin-up)?
- [ ] Hard refresh frontend (Ctrl+Shift+R)?

---

## 🚨 **Common Errors**

### "Backend URL not configured"
→ Set `NEXT_PUBLIC_API_URL` in Vercel

### "Backend returned 502"
→ Backend is spinning up, wait 30-60 seconds

### "Invalid API key" in logs
→ Check Supabase Service Role Key in Render

### "No news right now"
→ Click "Fetch Latest Batch" to trigger data fetch

---

## 📞 **Still Not Working?**

1. Check Render logs for backend errors
2. Check Vercel logs for frontend errors
3. Check browser console (F12) for client errors
4. Verify all environment variables are set correctly


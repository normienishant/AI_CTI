# 🔧 Backend 502 Error - Quick Fix Guide

## ❌ **Problem: Backend showing 502 Bad Gateway**

### **Common Causes:**

1. **Free Tier Spin-Down** (Most Common)
   - Render free tier spins down after 15 minutes of inactivity
   - First request takes 30-60 seconds to wake up

2. **Supabase Connection Error**
   - Invalid API key
   - Network timeout
   - Supabase service down

3. **Application Crash on Startup**
   - Import errors
   - Missing dependencies
   - Environment variables missing

---

## ✅ **Quick Fixes:**

### **Fix 1: Check Render Logs**

1. Go to Render dashboard
2. Click your service
3. Go to **Logs** tab
4. Check for errors:
   - "Supabase connection failed"
   - "Import error"
   - "Port binding error"

### **Fix 2: Verify Environment Variables**

Render dashboard → Environment Variables → Check:

- ✅ `SUPABASE_URL` - Should be `https://xxxxx.supabase.co`
- ✅ `SUPABASE_SERVICE_KEY` - Should be long key starting with `eyJ...`
- ✅ `SUPABASE_KEY` - Same as `SUPABASE_SERVICE_KEY`

### **Fix 3: Manual Redeploy**

1. Render dashboard → Your service
2. **Manual Deploy** → **Deploy latest commit**
3. Wait 5-10 minutes
4. Check logs for "Application startup complete"

### **Fix 4: Test Backend Directly**

Open in browser:
```
https://ai-cti-1-8c7w.onrender.com/
```

Should return:
```json
{
  "status": "ok",
  "service": "AI-CTI API",
  ...
}
```

If 502, wait 30-60 seconds and try again (free tier spin-up).

---

## 🔍 **Debug Steps:**

### **Step 1: Check Service Status**
- Render dashboard → Service status
- Should be "Live" (green)
- If "Stopped" or "Failed", check logs

### **Step 2: Check Recent Logs**
Look for:
- ✅ "Application startup complete" = Good
- ❌ "Error" or "Traceback" = Problem
- ❌ "Supabase connection failed" = Check credentials

### **Step 3: Test Endpoints**

1. **Root endpoint:**
   ```
   https://ai-cti-1-8c7w.onrender.com/
   ```

2. **Results endpoint:**
   ```
   https://ai-cti-1-8c7w.onrender.com/results
   ```

3. **Docs endpoint:**
   ```
   https://ai-cti-1-8c7w.onrender.com/docs
   ```

---

## 🚨 **If Still 502:**

### **Option 1: Wait for Spin-Up (Free Tier)**
- Wait 30-60 seconds
- Refresh the page
- First request after spin-down takes time

### **Option 2: Check Supabase**
- Supabase dashboard → Check if project is active
- Verify API keys are correct
- Check if tables exist

### **Option 3: Redeploy**
- Render dashboard → Manual Deploy
- Or push a new commit to trigger auto-deploy

---

## ✅ **Prevention:**

1. **Use GitHub Actions for auto-fetch** (keeps backend warm)
2. **Upgrade to paid tier** (always-on instance)
3. **Add health check endpoint** (ping every 5 minutes)

---

## 📝 **Current Status Check:**

Run these commands to check:

```bash
# Test backend root
curl https://ai-cti-1-8c7w.onrender.com/

# Test results endpoint
curl https://ai-cti-1-8c7w.onrender.com/results

# Check if it's responding
```

If all return 502, backend is down. Check Render logs!


# 🛑 Disable Auto-Deploy on Render

## **Option 1: Disable Auto-Deploy in Render (Recommended)**

### **Steps:**

1. **Go to Render Dashboard:**
   - https://dashboard.render.com
   - Click your service (AI_CTI-1)

2. **Go to Settings:**
   - Click **"Settings"** tab (top menu)

3. **Disable Auto-Deploy:**
   - Scroll down to **"Auto-Deploy"** section
   - Toggle **"Auto-Deploy"** to **OFF**
   - Click **"Save Changes"**

4. **Done!**
   - Now deployments will only happen when you manually trigger them
   - Go to **"Manual Deploy"** → **"Deploy latest commit"** when you want to deploy

---

## **Option 2: Use Manual Deploy Only**

### **How it works:**
- Auto-deploy OFF = No automatic deployments
- You manually trigger deployments when needed
- More control over when updates go live

### **When to deploy manually:**
- After making code changes
- After fixing bugs
- When you're ready to update production

---

## **Option 3: Deploy Specific Branch Only**

### **Steps:**

1. Render Settings → **"Auto-Deploy"** section
2. Set **"Branch"** to a specific branch (e.g., `production`)
3. Only pushes to that branch will trigger auto-deploy
4. Other branches won't auto-deploy

---

## **Current Setup:**

Right now, Render is set to:
- ✅ Auto-deploy on every `git push` to `main` branch
- This is why it redeploys automatically

---

## **Recommendation:**

**Keep auto-deploy ON** because:
- ✅ Easy workflow (just push to GitHub)
- ✅ Always up-to-date
- ✅ No manual steps needed

**But if you want control:**
- ✅ Turn OFF auto-deploy
- ✅ Deploy manually when ready
- ✅ Test changes before deploying

---

## **Quick Toggle:**

**To disable:**
1. Render → Service → Settings
2. Auto-Deploy → Toggle OFF
3. Save

**To enable again:**
1. Render → Service → Settings
2. Auto-Deploy → Toggle ON
3. Save

---

## **Note:**

- Frontend (Vercel) auto-deploy is separate
- You can disable that too in Vercel settings if needed
- But usually auto-deploy is helpful for development


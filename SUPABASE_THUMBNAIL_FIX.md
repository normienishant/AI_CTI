# Supabase Thumbnail Fix Guide

## Problem
Thumbnails are not appearing in the frontend even though images are being uploaded to Supabase.

## Root Causes
1. **Bucket doesn't exist** - The `article-thumbnails` bucket hasn't been created
2. **Bucket is not public** - The bucket exists but is set to private
3. **Missing storage policies** - No public read policy configured
4. **Wrong bucket name** - Environment variable mismatch

## Quick Fix Steps

### Step 1: Check Current Status
Run the diagnostic script:
```bash
cd ai_cti
python check_supabase_storage.py
```

This will tell you exactly what's wrong.

### Step 2: Create/Configure Bucket in Supabase

1. **Go to Supabase Dashboard**
   - Navigate to: https://supabase.com/dashboard
   - Select your project

2. **Go to Storage**
   - Click on "Storage" in the left sidebar

3. **Create Bucket (if it doesn't exist)**
   - Click "New bucket"
   - **Name**: `article-thumbnails` (must match exactly)
   - **Toggle "Public bucket" to ON** ⚠️ THIS IS CRITICAL!
   - Click "Create bucket"

4. **If Bucket Already Exists**
   - Click on the `article-thumbnails` bucket
   - Make sure "Public bucket" toggle is **ON**
   - If it's OFF, toggle it ON

### Step 3: Verify Storage Policies

1. **Go to Storage Policies**
   - In the bucket page, click on "Policies" tab

2. **Check for Public Read Policy**
   - There should be a policy allowing public read access
   - If not, create one:
     - Click "New policy"
     - Choose "For full customization"
     - Policy name: `Public read access`
     - Allowed operation: `SELECT`
     - Target roles: `anon`, `authenticated`
     - USING expression: `true`
     - WITH CHECK expression: `true`
     - Click "Review" then "Save policy"

### Step 4: Verify Environment Variables

Make sure these are set correctly:
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
SUPABASE_IMAGE_BUCKET=article-thumbnails
```

**Important**: Use the **service role key** (not the anon key) for `SUPABASE_KEY` in your backend.

### Step 5: Test the Fix

1. **Run diagnostic again**:
   ```bash
   python check_supabase_storage.py
   ```
   Should show all green checkmarks ✓

2. **Run ingestion**:
   ```bash
   python data_ingest/live_ingest_supabase.py
   ```
   Check logs for `[image] ✓✓✓` messages

3. **Check frontend**:
   - Restart your backend
   - Refresh frontend
   - Thumbnails should now appear

## Common Issues

### Issue: "Bucket not found"
**Solution**: Create the bucket as described in Step 2

### Issue: "403 Forbidden" when accessing URLs
**Solution**: 
- Make sure "Public bucket" toggle is ON
- Add storage policy for public read access

### Issue: "404 Not Found" for uploaded images
**Solution**:
- Check that files are actually being uploaded (check Supabase Storage → Files)
- Verify the URL format matches: `https://[project].supabase.co/storage/v1/object/public/article-thumbnails/[filename]`

### Issue: Images upload but URLs don't work
**Solution**:
- Wait a few seconds after upload (Supabase needs time to process)
- Check bucket is public
- Verify URL construction in logs

## Verification Checklist

- [ ] Bucket `article-thumbnails` exists in Supabase
- [ ] Bucket is set to **PUBLIC** (toggle ON)
- [ ] Storage policy allows public read (SELECT operation)
- [ ] Environment variable `SUPABASE_IMAGE_BUCKET=article-thumbnails` is set
- [ ] Using service role key (not anon key) for backend
- [ ] Diagnostic script shows all checks passing
- [ ] Ingestion logs show successful uploads
- [ ] Frontend displays thumbnails

## Still Not Working?

1. **Check backend logs** for `[image]` messages
2. **Check browser console** for image loading errors
3. **Check Supabase Storage** to see if files are actually uploaded
4. **Test a URL directly** in browser - should show image or 404 (not 403)
5. **Run diagnostic script** and share the output

## Need Help?

Share the output of:
```bash
python check_supabase_storage.py
```

This will show exactly what needs to be fixed.


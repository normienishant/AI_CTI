# How to Check Backend Logs for Thumbnail Issues

## For Render.com (Free Tier)

### Method 1: Render Dashboard
1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click on your service (e.g., `AI_CTI-1`)
3. Click on **"Logs"** in the left sidebar
4. You'll see real-time logs from your backend
5. Look for these log messages:
   - `[image]` - Image upload/download messages
   - `[article]` - Article processing messages
   - `[supabase:image]` - Supabase storage operations
   - `[api]` - API endpoint logs

### Method 2: Render Shell (SSH)
1. In Render Dashboard, click **"Shell"** in the left sidebar
2. This opens a terminal to your running service
3. Run: `tail -f /var/log/app.log` (if logs are written to file)
4. Or check Python output directly

### Method 3: Render Events
1. Click **"Events"** in Render Dashboard
2. Shows deployment and runtime events
3. Check for errors during deployment

## For Local Development

### Terminal Output
If running locally:
```bash
# Backend logs will print directly to terminal
python -m uvicorn api.main:app --reload

# Or if using the ingestion script:
python -m ai_cti.data_ingest.live_ingest_supabase
```

## What to Look For

### ✅ Good Signs (Thumbnails Working)
```
[image] Extracted OG image: https://...
[image] Uploaded thumbnail: abc123.jpg
[image] Public URL generated: https://xyz.supabase.co/storage/v1/object/public/article-thumbnails/abc123.jpg
[article] ✓ Using Supabase thumbnail: https://...
[article] ✓ Final image_url set: https://...
[api] Articles with image_url: 35/40
```

### ❌ Bad Signs (Thumbnails Not Working)
```
[image] download failed for https://...: Connection timeout
[supabase:image] upload failed: Bucket not found
[supabase:image] public url failed: Permission denied
[article] ✗ Failed to upload thumbnail
[article] ⚠ No thumbnail for: ...
[api] Articles with image_url: 0/40
```

## Common Issues & Solutions

### Issue 1: "Bucket not found"
**Solution:** 
- Go to Supabase Dashboard → Storage
- Create bucket named `article-thumbnails`
- Set it to **Public** (important!)
- Add policy: Allow public read access

### Issue 2: "Permission denied" or "public url failed"
**Solution:**
- Check bucket is **Public** in Supabase
- Verify `SUPABASE_IMAGE_BUCKET` env var is set to `article-thumbnails`
- Check bucket policies allow public read

### Issue 3: "download failed" or "fetch failed"
**Solution:**
- Some websites block image scraping
- This is normal - script will fallback to OG image or default
- Check if OG image URL is accessible

### Issue 4: "Articles with image_url: 0/40"
**Solution:**
- Run ingestion script manually: `python -m ai_cti.data_ingest.live_ingest_supabase`
- Check logs for why images aren't being uploaded
- Verify Supabase credentials are set correctly

## Debugging Steps

1. **Check if images are being extracted:**
   - Look for `[image] Extracted OG image:` messages
   - If missing, OG image extraction is failing

2. **Check if images are being uploaded:**
   - Look for `[image] Uploaded thumbnail:` messages
   - If missing, upload is failing

3. **Check if public URLs are generated:**
   - Look for `[image] Public URL generated:` messages
   - If missing, URL generation is failing

4. **Check if image_url is saved to database:**
   - Look for `[article] ✓ Final image_url set:` messages
   - Check `[api] Articles with image_url: X/40` count

5. **Check frontend console:**
   - Open browser DevTools (F12)
   - Go to Console tab
   - Look for `[ArticleCard]` messages
   - Check Network tab for failed image requests

## Quick Test

Run this in your backend terminal/shell:
```python
# Test Supabase connection
from supabase import create_client
import os

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# Test bucket access
storage = supabase.storage.from_("article-thumbnails")
try:
    # Try to list files (should work if bucket exists and is accessible)
    files = storage.list()
    print(f"✓ Bucket accessible, {len(files)} files")
except Exception as e:
    print(f"✗ Bucket error: {e}")

# Test public URL generation
try:
    # Try to get public URL for a test file
    url = storage.get_public_url("test.jpg")
    print(f"✓ Public URL generation works: {url[:80]}")
except Exception as e:
    print(f"✗ Public URL error: {e}")
```


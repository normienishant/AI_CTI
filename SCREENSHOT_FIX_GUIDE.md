# Screenshot Fix Guide - Backend Redeploy Ke Baad Bhi Screenshots Nahi Aare

## Problem
Backend redeploy ke baad bhi screenshots nahi aa rahe hain.

## Solutions

### 1. Check Database (Diagnostic)
Pehle check karo ki database me kya hai:

```bash
cd ai_cti
python check_thumbnails_in_db.py
```

Ye script dikhayega:
- Kitne articles me `image_url` hai
- Kitne articles me `image_url` nahi hai
- Pehle 10 articles ka detail

### 2. Force Screenshot Generation
Agar articles me `image_url` nahi hai, to force screenshot generate karo:

```bash
cd ai_cti
python force_screenshot_update.py
```

Ye script:
- Articles without images dhundhega
- Unke liye screenshot generate karega
- Supabase me upload karega
- Database me update karega

### 3. Manual Fetch Trigger
Backend redeploy ke baad, manually fetch trigger karo:

**Option A: Frontend se**
1. Dashboard pe jao
2. "Fetch Latest Batch" button click karo
3. Wait karo (2-3 minutes)

**Option B: Backend API se**
```bash
curl -X POST https://your-backend-url/fetch_live
```

### 4. Check Backend Logs
Render dashboard me backend logs check karo:

1. Render dashboard → Your service → Logs
2. Look for:
   - `[screenshot]` logs
   - `[article]` logs
   - `[articles] Upserting` logs

Expected logs:
```
[screenshot] [Attempt 1/2] Trying microlink.io...
[screenshot] ✓✓✓ Got screenshot URL from microlink: ...
[article] ✓✓✓✓✓ SUCCESS: Uploaded fresh screenshot: ...
[articles] Upserting with on_conflict='link' - will UPDATE existing articles with new image_url
```

### 5. Verify Supabase Storage
Supabase dashboard me check karo:

1. Supabase Dashboard → Storage → `article-thumbnails` bucket
2. Check if files are being uploaded
3. Verify bucket is **PUBLIC**

### 6. Check API Response
Frontend console me check karo:

1. Open browser DevTools (F12)
2. Go to Network tab
3. Refresh dashboard
4. Check `/api/results` response
5. Look for `image_url` field in articles

Expected:
```json
{
  "feeds": [
    {
      "title": "...",
      "image_url": "https://...supabase.co/storage/v1/object/public/article-thumbnails/...",
      ...
    }
  ]
}
```

## Recent Changes Made

1. **Screenshot Service Improvements:**
   - Retry logic for microlink.io (2 attempts)
   - Better error handling
   - Rate limit handling
   - Delay between requests (0.5s)

2. **Priority Logic:**
   - Check if article exists in DB
   - If no `image_url`, prioritize screenshot service
   - Always try screenshot service as fallback

3. **Database Updates:**
   - `ignore_duplicates=False` ensures existing articles get updated
   - `image_url` field is always updated on upsert

## Troubleshooting

### Issue: Screenshots generate ho rahe hain but database me save nahi ho rahe
**Solution:** Check upsert logs. Make sure `ignore_duplicates=False` is set.

### Issue: Screenshot service rate limited ho raha hai
**Solution:** Script me delay add kiya hai (0.5s). Agar still rate limit ho, to wait karo 1-2 minutes.

### Issue: Screenshots upload ho rahe hain but frontend me nahi dikh rahe
**Solution:** 
1. Check if Supabase bucket is PUBLIC
2. Check browser console for image load errors
3. Verify `image_url` in API response

### Issue: Backend logs me errors aa rahe hain
**Solution:** Check specific error:
- `Bucket not found` → Create bucket in Supabase
- `Permission denied` → Check Supabase storage policies
- `Timeout` → Screenshot service might be slow, wait and retry

## Next Steps

1. ✅ Run `check_thumbnails_in_db.py` to see current state
2. ✅ Run `force_screenshot_update.py` to generate screenshots for existing articles
3. ✅ Trigger manual fetch from frontend
4. ✅ Check backend logs for screenshot generation
5. ✅ Verify Supabase storage bucket is public
6. ✅ Check frontend console for image URLs

## Expected Timeline

- **Screenshot generation:** 1-2 seconds per article
- **Upload to Supabase:** 0.5-1 second per image
- **Database update:** Instant
- **Total for 10 articles:** ~20-30 seconds

## Contact

Agar still issues hain, to:
1. Backend logs share karo
2. Database check script output share karo
3. Frontend console errors share karo


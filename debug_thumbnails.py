#!/usr/bin/env python3
"""
Debug script to check thumbnail URLs in database and API
"""

import os
import sys
import requests
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
API_URL = os.getenv("API_URL", "http://localhost:8000")

print("=" * 70)
print("THUMBNAIL DEBUG SCRIPT")
print("=" * 70)
print()

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Missing Supabase credentials!")
    sys.exit(1)

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✓ Supabase client created")
except Exception as e:
    print(f"❌ Failed to create Supabase client: {e}")
    sys.exit(1)

# Check database directly
print()
print("[1] Checking database for articles with image_url...")
try:
    response = supabase.table("articles").select("id,title,link,image_url").limit(10).execute()
    articles = response.data or []
    
    print(f"   Found {len(articles)} articles")
    
    articles_with_images = [a for a in articles if a.get("image_url")]
    articles_without_images = [a for a in articles if not a.get("image_url")]
    
    print(f"   ✓ Articles WITH image_url: {len(articles_with_images)}")
    print(f"   ✗ Articles WITHOUT image_url: {len(articles_without_images)}")
    
    if articles_with_images:
        print()
        print("   Sample articles WITH image_url:")
        for i, art in enumerate(articles_with_images[:5], 1):
            img_url = art.get("image_url", "")
            print(f"   {i}. {art.get('title', '')[:50]}")
            print(f"      URL: {img_url[:100]}")
            
            # Test if URL is accessible
            if img_url:
                try:
                    resp = requests.head(img_url, timeout=5, allow_redirects=True)
                    status = "✓" if resp.status_code == 200 else f"✗ ({resp.status_code})"
                    print(f"      Status: {status}")
                except Exception as e:
                    print(f"      Status: ✗ Error: {str(e)[:50]}")
            print()
    
    if articles_without_images:
        print()
        print("   Sample articles WITHOUT image_url:")
        for i, art in enumerate(articles_without_images[:3], 1):
            print(f"   {i}. {art.get('title', '')[:50]}")
            print(f"      Link: {art.get('link', '')[:80]}")
        print()
        
except Exception as e:
    print(f"   ❌ Error querying database: {e}")
    import traceback
    traceback.print_exc()

# Check API endpoint
print()
print("[2] Checking API /results endpoint...")
try:
    resp = requests.get(f"{API_URL}/results", timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        feeds = data.get("feeds", [])
        print(f"   ✓ API returned {len(feeds)} articles")
        
        feeds_with_images = [f for f in feeds if f.get("image_url") or f.get("image")]
        feeds_without_images = [f for f in feeds if not f.get("image_url") and not f.get("image")]
        
        print(f"   ✓ Feeds WITH image: {len(feeds_with_images)}")
        print(f"   ✗ Feeds WITHOUT image: {len(feeds_without_images)}")
        
        if feeds_with_images:
            print()
            print("   Sample feeds WITH image from API:")
            for i, feed in enumerate(feeds_with_images[:5], 1):
                img = feed.get("image_url") or feed.get("image") or ""
                print(f"   {i}. {feed.get('title', '')[:50]}")
                print(f"      image_url: {feed.get('image_url', 'NONE')[:100] if feed.get('image_url') else 'NONE'}")
                print(f"      image: {feed.get('image', 'NONE')[:100] if feed.get('image') else 'NONE'}")
                if img:
                    try:
                        resp = requests.head(img, timeout=5, allow_redirects=True)
                        status = "✓" if resp.status_code == 200 else f"✗ ({resp.status_code})"
                        print(f"      Status: {status}")
                    except Exception as e:
                        print(f"      Status: ✗ Error: {str(e)[:50]}")
                print()
        
        if feeds_without_images:
            print()
            print("   Sample feeds WITHOUT image from API:")
            for i, feed in enumerate(feeds_without_images[:3], 1):
                print(f"   {i}. {feed.get('title', '')[:50]}")
                print(f"      Keys: {list(feed.keys())}")
        print()
    else:
        print(f"   ❌ API returned status {resp.status_code}")
        print(f"   Response: {resp.text[:200]}")
except Exception as e:
    print(f"   ❌ Error calling API: {e}")
    print(f"   Make sure backend is running at {API_URL}")

# Check storage bucket
print()
print("[3] Checking storage bucket for files...")
try:
    SUPABASE_IMAGE_BUCKET = os.getenv("SUPABASE_IMAGE_BUCKET", "article-thumbnails")
    image_storage = supabase.storage.from_(SUPABASE_IMAGE_BUCKET)
    files = image_storage.list()
    
    file_count = len(files) if isinstance(files, list) else 0
    print(f"   Found {file_count} files in bucket '{SUPABASE_IMAGE_BUCKET}'")
    
    if file_count > 0:
        print()
        print("   Sample files in bucket:")
        sample_files = files[:5] if isinstance(files, list) else []
        for i, file_info in enumerate(sample_files, 1):
            file_name = file_info.get("name") if isinstance(file_info, dict) else str(file_info)
            test_url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{SUPABASE_IMAGE_BUCKET}/{file_name}"
            print(f"   {i}. {file_name[:60]}")
            try:
                resp = requests.head(test_url, timeout=5, allow_redirects=True)
                status = "✓" if resp.status_code == 200 else f"✗ ({resp.status_code})"
                print(f"      URL: {test_url[:80]}")
                print(f"      Status: {status}")
            except Exception as e:
                print(f"      Status: ✗ Error: {str(e)[:50]}")
            print()
    else:
        print("   ⚠️  No files found in bucket!")
        print("   This means images are not being uploaded.")
        print("   Check ingestion logs for upload errors.")
except Exception as e:
    print(f"   ❌ Error checking storage: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 70)
print("DIAGNOSIS SUMMARY")
print("=" * 70)
print()
print("Check the above output to identify the issue:")
print()
print("1. If database has image_url but API doesn't return them:")
print("   → Check /results endpoint in api/main.py")
print()
print("2. If database doesn't have image_url:")
print("   → Check ingestion logs for upload errors")
print("   → Run: python data_ingest/live_ingest_supabase.py")
print()
print("3. If storage bucket is empty:")
print("   → Images are not being uploaded")
print("   → Check upload function and bucket permissions")
print()
print("4. If URLs exist but return 403/404:")
print("   → Bucket is not public or policy issue")
print("   → Check Supabase Dashboard → Storage → Policies")
print()
print("=" * 70)


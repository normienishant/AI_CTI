#!/usr/bin/env python3
"""
Comprehensive Supabase Storage Diagnostic Script
Checks bucket existence, permissions, and public access for thumbnails.
"""

import os
import sys
import requests
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_IMAGE_BUCKET = os.getenv("SUPABASE_IMAGE_BUCKET", "article-thumbnails")

print("=" * 70)
print("SUPABASE STORAGE DIAGNOSTIC TOOL")
print("=" * 70)
print()

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ ERROR: Missing Supabase credentials!")
    print(f"   SUPABASE_URL: {'SET' if SUPABASE_URL else 'NOT SET'}")
    print(f"   SUPABASE_KEY: {'SET' if SUPABASE_KEY else 'NOT SET'}")
    print()
    print("Please set these environment variables and try again.")
    sys.exit(1)

print(f"✓ SUPABASE_URL: {SUPABASE_URL[:50]}...")
print(f"✓ SUPABASE_KEY: {'*' * 20}...{SUPABASE_KEY[-4:] if len(SUPABASE_KEY) > 4 else '****'}")
print(f"✓ Target bucket: {SUPABASE_IMAGE_BUCKET}")
print()

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("[1] ✓ Supabase client created successfully")
except Exception as e:
    print(f"[1] ❌ Failed to create Supabase client: {e}")
    sys.exit(1)

# Check bucket existence
print()
print("[2] Checking bucket existence...")
try:
    buckets = supabase.storage.list_buckets()
    bucket_names = [b.name for b in buckets]
    bucket_info = {b.name: b for b in buckets}
    
    print(f"   Found {len(bucket_names)} bucket(s): {', '.join(bucket_names)}")
    
    if SUPABASE_IMAGE_BUCKET not in bucket_names:
        print(f"   ❌ Bucket '{SUPABASE_IMAGE_BUCKET}' NOT FOUND!")
        print()
        print("   SOLUTION:")
        print(f"   1. Go to Supabase Dashboard → Storage")
        print(f"   2. Click 'New bucket'")
        print(f"   3. Name: {SUPABASE_IMAGE_BUCKET}")
        print(f"   4. Make it PUBLIC (toggle 'Public bucket' ON)")
        print(f"   5. Click 'Create bucket'")
        sys.exit(1)
    else:
        bucket = bucket_info[SUPABASE_IMAGE_BUCKET]
        print(f"   ✓ Bucket '{SUPABASE_IMAGE_BUCKET}' exists")
        # Check if bucket is public (this might not be directly available in the API)
        print(f"   Note: Public status must be checked in Supabase Dashboard")
except Exception as e:
    print(f"   ❌ Error checking buckets: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test upload
print()
print("[3] Testing upload capability...")
try:
    test_content = b"test image content"
    test_key = "test_thumbnail_check.jpg"
    image_storage = supabase.storage.from_(SUPABASE_IMAGE_BUCKET)
    
    # Try to upload a test file
    image_storage.upload(test_key, test_content, file_options={"upsert": "true"})
    print(f"   ✓ Upload test successful: {test_key}")
    
    # Try to get public URL
    try:
        public_url = image_storage.get_public_url(test_key)
        if isinstance(public_url, dict):
            public_url = public_url.get("publicUrl") or public_url.get("publicURL")
        print(f"   ✓ Got public URL from API: {public_url[:80]}...")
    except Exception as url_err:
        print(f"   ⚠️  Could not get public URL from API: {url_err}")
        # Construct manually
        clean_url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{SUPABASE_IMAGE_BUCKET}/{test_key}"
        public_url = clean_url
        print(f"   Using manual URL: {public_url[:80]}...")
    
    # Test if URL is accessible (public read)
    print()
    print("[4] Testing public URL accessibility...")
    try:
        resp = requests.head(public_url, timeout=10, allow_redirects=True)
        if resp.status_code == 200:
            print(f"   ✓✓✓ SUCCESS! Public URL is accessible (status: {resp.status_code})")
            print(f"   URL: {public_url}")
        elif resp.status_code == 404:
            print(f"   ❌ URL returned 404 - File not found or bucket not public")
            print()
            print("   SOLUTION:")
            print(f"   1. Go to Supabase Dashboard → Storage → {SUPABASE_IMAGE_BUCKET}")
            print(f"   2. Make sure 'Public bucket' toggle is ON")
            print(f"   3. Go to 'Policies' tab")
            print(f"   4. Create a policy with:")
            print(f"      - Policy name: 'Public read access'")
            print(f"      - Allowed operation: SELECT")
            print(f"      - Target roles: anon, authenticated")
            print(f"      - USING expression: true")
            print(f"      - WITH CHECK expression: true")
        elif resp.status_code == 403:
            print(f"   ❌ URL returned 403 - Permission denied (bucket not public)")
            print()
            print("   SOLUTION:")
            print(f"   1. Go to Supabase Dashboard → Storage → {SUPABASE_IMAGE_BUCKET}")
            print(f"   2. Toggle 'Public bucket' to ON")
            print(f"   3. Or create a storage policy for public read access")
        else:
            print(f"   ⚠️  Unexpected status code: {resp.status_code}")
    except Exception as access_err:
        print(f"   ❌ Could not access URL: {access_err}")
        print()
        print("   This might indicate:")
        print("   - Bucket is not set to public")
        print("   - Network/firewall issue")
        print("   - URL construction issue")
    
    # Clean up test file
    try:
        image_storage.remove([test_key])
        print()
        print(f"   ✓ Cleaned up test file: {test_key}")
    except:
        pass
        
except Exception as e:
    print(f"   ❌ Upload test failed: {e}")
    import traceback
    traceback.print_exc()
    print()
    print("   This might indicate:")
    print("   - Insufficient permissions (need service role key)")
    print("   - Bucket doesn't exist")
    print("   - Network issue")

# Check existing files
print()
print("[5] Checking existing files in bucket...")
try:
    files = image_storage.list()
    file_count = len(files) if isinstance(files, list) else 0
    print(f"   Found {file_count} file(s) in bucket")
    
    if file_count > 0:
        # Test first few files
        sample_files = files[:3] if isinstance(files, list) else []
        for file_info in sample_files:
            file_name = file_info.get("name") if isinstance(file_info, dict) else str(file_info)
            test_url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{SUPABASE_IMAGE_BUCKET}/{file_name}"
            try:
                resp = requests.head(test_url, timeout=5)
                status = "✓" if resp.status_code == 200 else f"✗ ({resp.status_code})"
                print(f"   {status} {file_name[:50]}")
            except:
                print(f"   ✗ {file_name[:50]} (error)")
except Exception as e:
    print(f"   ⚠️  Could not list files: {e}")

print()
print("=" * 70)
print("DIAGNOSTIC COMPLETE")
print("=" * 70)
print()
print("NEXT STEPS:")
print("1. If bucket doesn't exist, create it in Supabase Dashboard")
print("2. Make sure bucket is PUBLIC (toggle 'Public bucket' ON)")
print("3. Verify storage policies allow public read access")
print("4. Run the ingestion script again: python data_ingest/live_ingest_supabase.py")
print()


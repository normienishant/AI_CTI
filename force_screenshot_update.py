#!/usr/bin/env python3
"""Force screenshot generation for articles without image_url"""

import os
import sys
from supabase import create_client, Client
from dotenv import load_dotenv

# Add parent directory to path to import from data_ingest
sys.path.insert(0, os.path.dirname(__file__))

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ SUPABASE_URL or SUPABASE_KEY not set!")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Import screenshot function
from data_ingest.live_ingest_supabase import _get_screenshot_url, _upload_image_to_supabase

print("=" * 80)
print("FORCE SCREENSHOT UPDATE FOR ARTICLES WITHOUT IMAGES")
print("=" * 80)

# Get articles without image_url
try:
    response = supabase.table("articles").select("id, title, link, image_url").order("fetched_at", desc=True).limit(50).execute()
    
    if not response.data:
        print("❌ No articles found in database!")
        exit(1)
    
    articles = response.data
    articles_without_images = [a for a in articles if not a.get("image_url") or not a.get("image_url").strip()]
    
    print(f"\n📊 Found {len(articles_without_images)} articles without images (out of {len(articles)} total)")
    
    if len(articles_without_images) == 0:
        print("✅ All articles already have images!")
        exit(0)
    
    print(f"\n🔄 Processing {min(10, len(articles_without_images))} articles...")
    print("-" * 80)
    
    updated_count = 0
    failed_count = 0
    
    for i, article in enumerate(articles_without_images[:10], 1):  # Process first 10
        title = article.get("title", "No title")[:60]
        link = article.get("link", "")
        article_id = article.get("id")
        
        if not link:
            print(f"{i}. ✗ Skipping (no link): {title}")
            continue
        
        print(f"\n{i}. Processing: {title}")
        print(f"   Link: {link[:80]}")
        
        try:
            # Get screenshot
            import time
            time.sleep(1)  # Delay to avoid rate limits
            screenshot_url = _get_screenshot_url(link)
            
            if screenshot_url:
                print(f"   ✓ Got screenshot URL: {screenshot_url[:80]}")
                
                # Upload to Supabase
                uploaded_url = _upload_image_to_supabase(screenshot_url)
                
                if uploaded_url:
                    print(f"   ✓✓✓ Uploaded to Supabase: {uploaded_url[:80]}")
                    
                    # Update database
                    update_response = supabase.table("articles").update({
                        "image_url": uploaded_url
                    }).eq("id", article_id).execute()
                    
                    if update_response.data:
                        print(f"   ✅✅✅ Database updated successfully!")
                        updated_count += 1
                    else:
                        print(f"   ⚠️  Database update returned no data")
                        failed_count += 1
                else:
                    print(f"   ✗ Failed to upload screenshot to Supabase")
                    failed_count += 1
            else:
                print(f"   ✗ Screenshot service returned no URL")
                failed_count += 1
                
        except Exception as e:
            print(f"   ✗✗✗ Error: {e}")
            import traceback
            traceback.print_exc()
            failed_count += 1
    
    print("\n" + "=" * 80)
    print(f"📊 SUMMARY:")
    print(f"   Updated: {updated_count}")
    print(f"   Failed: {failed_count}")
    print("=" * 80)
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()


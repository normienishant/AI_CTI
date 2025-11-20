#!/usr/bin/env python3
"""Check what image_urls are actually in the database and what the API returns"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ SUPABASE_URL or SUPABASE_KEY not set!")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("=" * 80)
print("CHECKING THUMBNAILS IN DATABASE")
print("=" * 80)

# Get recent articles
try:
    response = supabase.table("articles").select("id, title, link, image_url").order("fetched_at", desc=True).limit(20).execute()
    
    if not response.data:
        print("❌ No articles found in database!")
        exit(1)
    
    articles = response.data
    total = len(articles)
    with_images = sum(1 for a in articles if a.get("image_url") and a.get("image_url").strip())
    without_images = total - with_images
    
    print(f"\n📊 SUMMARY:")
    print(f"   Total articles checked: {total}")
    print(f"   Articles WITH image_url: {with_images} ({with_images*100//total if total > 0 else 0}%)")
    print(f"   Articles WITHOUT image_url: {without_images} ({without_images*100//total if total > 0 else 0}%)")
    
    print(f"\n📋 DETAILS (first 10 articles):")
    print("-" * 80)
    for i, article in enumerate(articles[:10], 1):
        title = article.get("title", "No title")[:60]
        link = article.get("link", "No link")[:60]
        image_url = article.get("image_url")
        
        if image_url and image_url.strip():
            img_preview = image_url[:80] if len(image_url) > 80 else image_url
            print(f"{i}. ✓ HAS IMAGE")
            print(f"   Title: {title}")
            print(f"   Image: {img_preview}")
            if "supabase.co" in image_url:
                print(f"   → Supabase storage URL")
            elif image_url.startswith("http"):
                print(f"   → External URL")
        else:
            print(f"{i}. ✗ NO IMAGE")
            print(f"   Title: {title}")
            print(f"   Link: {link}")
    
    # Check articles without images
    if without_images > 0:
        print(f"\n⚠️  ARTICLES WITHOUT IMAGES (first 5):")
        print("-" * 80)
        no_image_articles = [a for a in articles if not a.get("image_url") or not a.get("image_url").strip()][:5]
        for i, article in enumerate(no_image_articles, 1):
            print(f"{i}. {article.get('title', 'No title')[:60]}")
            print(f"   Link: {article.get('link', 'No link')[:80]}")
    
    print("\n" + "=" * 80)
    print("✅ Database check complete!")
    print("=" * 80)
    
except Exception as e:
    print(f"❌ Error checking database: {e}")
    import traceback
    traceback.print_exc()


/*
  app/api/preview/route.js
  Server-side route to fetch OG tags (title, description) from a URL
*/
export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const url = searchParams.get('url');
  
  if (!url) {
    return new Response(JSON.stringify({ error: 'Missing url parameter' }), {
      status: 400,
      headers: { 'content-type': 'application/json' },
    });
  }

  try {
    // Fetch the URL
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout
    
    const res = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      },
      signal: controller.signal,
    });
    
    clearTimeout(timeoutId);
    
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    
    const html = await res.text();
    
    // Simple regex-based extraction (for production, consider using cheerio or similar)
    const ogTitleMatch = html.match(/<meta\s+property=["']og:title["']\s+content=["']([^"']+)["']/i) ||
                        html.match(/<meta\s+name=["']twitter:title["']\s+content=["']([^"']+)["']/i);
    const ogDescMatch = html.match(/<meta\s+property=["']og:description["']\s+content=["']([^"']+)["']/i) ||
                        html.match(/<meta\s+name=["']twitter:description["']\s+content=["']([^"']+)["']/i);
    const titleMatch = html.match(/<title[^>]*>([^<]+)<\/title>/i);
    
    const title = ogTitleMatch?.[1] || titleMatch?.[1] || null;
    const description = ogDescMatch?.[1] || null;
    
    return new Response(JSON.stringify({ title, description }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  } catch (err) {
    // Return empty result instead of error to prevent frontend issues
    return new Response(JSON.stringify({ title: null, description: null }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  }
}


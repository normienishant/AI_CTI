/*
 app/api/results/route.js
 Server-side proxy: forwards requests to BACKEND_URL (default http://127.0.0.1:8000)
*/
export async function GET(request) {
  const BACKEND = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  
  // Better error message if backend URL not set
  if (!process.env.NEXT_PUBLIC_API_URL && process.env.NODE_ENV === 'production') {
    console.error("[api/results] NEXT_PUBLIC_API_URL not set in production!");
    return new Response(JSON.stringify({ 
      iocs: [],
      clusters: {},
      feeds: [],
      error: "Backend URL not configured. Please set NEXT_PUBLIC_API_URL in Vercel environment variables."
    }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }
  
  // Retry logic for free tier spin-down
  let lastError = null;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      // use global fetch (Next provides it) - always fetch fresh data
      // Create timeout controller for free tier spin-down handling
      const controller = new AbortController();
      const timeoutMs = attempt === 0 ? 30000 : 45000; // First try 30s, retries 45s
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
      
      const res = await fetch(`${BACKEND}/results`, { 
        cache: "no-store",
        next: { revalidate: 0 },
        headers: {
          "Content-Type": "application/json",
          "Cache-Control": "no-cache, no-store, must-revalidate",
        },
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);
      
      if (!res.ok) {
        // 502/503/504 are retryable
        if (res.status >= 502 && res.status <= 504 && attempt < 2) {
          console.log(`[api/results] Backend returned ${res.status}, retrying (attempt ${attempt + 1}/3)...`);
          await new Promise(resolve => setTimeout(resolve, 2000 * (attempt + 1))); // Exponential backoff
          lastError = new Error(`Backend returned ${res.status}: ${res.statusText}`);
          continue;
        }
        throw new Error(`Backend returned ${res.status}: ${res.statusText}`);
      }
      
      const json = await res.json();
      return new Response(JSON.stringify(json), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    } catch (err) {
      lastError = err;
      // Retry on network errors or abort errors (but not on 4xx errors)
      if (attempt < 2 && (err.name === 'AbortError' || err.message?.includes('fetch'))) {
        console.log(`[api/results] Network error, retrying (attempt ${attempt + 1}/3)...`);
        await new Promise(resolve => setTimeout(resolve, 2000 * (attempt + 1)));
        continue;
      }
      break;
    }
  }
  
  // All retries failed
  console.error("[api/results] Error after retries:", lastError);
  const errorMsg = lastError?.name === 'AbortError' 
    ? "Backend is taking too long to respond. It might be spinning up (free tier). Please wait 30-60 seconds and refresh."
    : lastError?.message || "Failed to connect to backend after 3 attempts";
  
  // Return empty data structure instead of error to prevent frontend crash
  return new Response(JSON.stringify({ 
    iocs: [],
    clusters: {},
    feeds: [],
    error: errorMsg 
  }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

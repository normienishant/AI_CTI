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
  
  try {
    // use global fetch (Next provides it) - always fetch fresh data
    // Create timeout controller for free tier spin-down handling
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout
    
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
      throw new Error(`Backend returned ${res.status}: ${res.statusText}`);
    }
    
    const json = await res.json();
    return new Response(JSON.stringify(json), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  } catch (err) {
    console.error("[api/results] Error:", err);
    const errorMsg = err.name === 'AbortError' 
      ? "Backend is taking too long to respond. It might be spinning up (free tier). Please wait 30-60 seconds and refresh."
      : err.message || "Failed to connect to backend";
    
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
}

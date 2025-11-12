/*
 app/api/results/route.js
 Server-side proxy: forwards requests to BACKEND_URL (default http://127.0.0.1:8000)
*/
export async function GET(request) {
  const BACKEND = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  try {
    // use global fetch (Next provides it)
    const res = await fetch(`${BACKEND}/results`, { 
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
      },
    });
    
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
    // Return empty data structure instead of error to prevent frontend crash
    return new Response(JSON.stringify({ 
      iocs: [],
      clusters: {},
      feeds: [],
      error: err.message 
    }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }
}

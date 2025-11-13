export async function GET(request) {
  const { searchParams } = request.nextUrl;
  const link = searchParams.get('link');
  const BACKEND = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

  if (!link) {
    return new Response(
      JSON.stringify({ error: 'Missing link parameter', article: null }),
      {
        status: 400,
        headers: { 'content-type': 'application/json' },
      }
    );
  }

  try {
    const res = await fetch(`${BACKEND}/article?link=${encodeURIComponent(link)}`, {
      cache: 'no-store',
    });

    if (!res.ok) {
      throw new Error(`Backend returned ${res.status}: ${res.statusText}`);
    }

    const json = await res.json();
    return new Response(JSON.stringify(json), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  } catch (err) {
    console.error('[api/article] Error:', err);
    return new Response(
      JSON.stringify({ article: null, error: err.message || 'Failed to load article.' }),
      {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }
    );
  }
}

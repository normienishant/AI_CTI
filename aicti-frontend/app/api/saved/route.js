import { NextResponse } from 'next/server';

const BACKEND = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

function buildUrl(path, params = {}) {
  const url = new URL(`${BACKEND}${path}`);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      url.searchParams.set(key, value);
    }
  });
  return url;
}

export async function GET(request) {
  const clientId = request.nextUrl.searchParams.get('clientId');
  if (!clientId) {
    return NextResponse.json({ items: [], error: 'clientId is required' }, { status: 400 });
  }

  try {
    const url = buildUrl('/saved', { client_id: clientId });
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) {
      throw new Error(`Backend returned ${res.status}`);
    }
    const json = await res.json();
    return NextResponse.json(json);
  } catch (err) {
    console.error('[api/saved] GET error:', err);
    return NextResponse.json({ items: [], error: err.message || 'Failed to load saved briefings.' }, { status: 200 });
  }
}

export async function POST(request) {
  try {
    const body = await request.json();
    if (!body?.client_id || !body?.link) {
      return NextResponse.json({ error: 'client_id and link are required' }, { status: 400 });
    }

    const res = await fetch(`${BACKEND}/saved`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      cache: 'no-store',
    });

    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`Backend returned ${res.status}: ${errorText}`);
    }

    const json = await res.json();
    return NextResponse.json(json);
  } catch (err) {
    console.error('[api/saved] POST error:', err);
    return NextResponse.json({ error: err.message || 'Failed to save briefing.' }, { status: 500 });
  }
}

export async function DELETE(request) {
  const { searchParams } = request.nextUrl;
  const clientId = searchParams.get('clientId');
  const link = searchParams.get('link');

  if (!clientId || !link) {
    return NextResponse.json({ error: 'clientId and link are required' }, { status: 400 });
  }

  try {
    const url = buildUrl('/saved', { client_id: clientId, link });
    const res = await fetch(url, { method: 'DELETE', cache: 'no-store' });
    if (!res.ok) {
      throw new Error(`Backend returned ${res.status}`);
    }
    const json = await res.json();
    return NextResponse.json(json);
  } catch (err) {
    console.error('[api/saved] DELETE error:', err);
    return NextResponse.json({ error: err.message || 'Failed to remove saved briefing.' }, { status: 500 });
  }
}

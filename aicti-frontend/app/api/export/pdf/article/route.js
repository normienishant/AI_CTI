import { NextResponse } from 'next/server';

const BACKEND = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export async function GET(request) {
  const { searchParams } = request.nextUrl;
  const clientId = searchParams.get('clientId');
  const link = searchParams.get('link');

  if (!clientId || !link) {
    return NextResponse.json({ error: 'clientId and link are required' }, { status: 400 });
  }

  try {
    const url = `${BACKEND}/export/pdf/article?client_id=${encodeURIComponent(clientId)}&link=${encodeURIComponent(link)}`;
    const res = await fetch(url, { cache: 'no-store' });

    if (!res.ok) {
      const errorText = await res.text();
      console.error('[api/export/pdf/article] Backend error:', errorText);
      throw new Error(`Backend returned ${res.status}`);
    }

    const blob = await res.blob();
    return new NextResponse(blob, {
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': `attachment; filename="ai-cti-article-${new Date().toISOString().split('T')[0]}.pdf"`,
      },
    });
  } catch (err) {
    console.error('[api/export/pdf/article] Error:', err);
    return NextResponse.json({ error: err.message || 'Failed to generate PDF.' }, { status: 500 });
  }
}


import { Suspense } from 'react';
import StoryClient from './StoryClient';

async function fetchArticle(link) {
  if (!link) return null;
  const backend = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
  const res = await fetch(`${backend}/article?link=${encodeURIComponent(link)}`, {
    cache: 'no-store',
  });
  if (!res.ok) return null;
  const json = await res.json();
  return json.article || null;
}

function StoryFallback() {
  return (
    <section className="container" style={{ padding: '60px 24px', maxWidth: 900 }}>
      <div className="sidebar-card">Preparing intelligence briefing…</div>
    </section>
  );
}

export default async function StoryPage({ searchParams }) {
  const link = searchParams?.link || '';
  const serverArticle = await fetchArticle(link);

  return (
    <Suspense fallback={<StoryFallback />}>
      <StoryClient initialArticle={serverArticle} linkParam={link} />
    </Suspense>
  );
}

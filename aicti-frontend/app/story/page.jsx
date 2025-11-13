import { Suspense } from 'react';
import StoryClient from './StoryClient';

function StoryFallback() {
  return (
    <section className="container" style={{ padding: '60px 24px', maxWidth: 900 }}>
      <div className="sidebar-card">Preparing intelligence briefing…</div>
    </section>
  );
}

export default function StoryPage() {
  return (
    <Suspense fallback={<StoryFallback />}>
      <StoryClient />
    </Suspense>
  );
}

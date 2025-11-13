'use client';

import { useEffect, useMemo, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';

function formatTimestamp(value) {
  if (!value) return 'Unknown';
  try {
    return new Intl.DateTimeFormat('en', {
      dateStyle: 'long',
      timeStyle: 'short',
    }).format(new Date(value));
  } catch {
    return value;
  }
}

export default function StoryPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const linkParam = searchParams.get('link');
  const [article, setArticle] = useState(null);
  const [related, setRelated] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!linkParam) {
      setError('Missing article link.');
      setLoading(false);
      return;
    }

    const controller = new AbortController();

    async function loadArticle() {
      try {
        setLoading(true);
        const res = await fetch(`/api/article?link=${encodeURIComponent(linkParam)}`, {
          signal: controller.signal,
        });
        const data = await res.json();
        if (data.error) {
          setError(data.error);
        } else {
          setArticle(data.article);
        }
      } catch (err) {
        if (err.name !== 'AbortError') {
          setError(err.message || 'Failed to load article.');
        }
      } finally {
        setLoading(false);
      }
    }

    async function loadRelated() {
      try {
        const res = await fetch('/api/results');
        const json = await res.json();
        setRelated(json.feeds || []);
      } catch (err) {
        console.warn('Failed to load related feeds', err);
      }
    }

    loadArticle();
    loadRelated();

    return () => controller.abort();
  }, [linkParam]);

  const relatedItems = useMemo(() => {
    if (!article || !related.length) return [];
    return related
      .filter((item) => item.link !== article.link)
      .slice(0, 6);
  }, [article, related]);

  if (!linkParam) {
    return (
      <section className="container" style={{ padding: '48px 24px', maxWidth: 900 }}>
        <div className="sidebar-card">
          Missing article reference. Head back to the <Link href="/dashboard">live desk</Link>.
        </div>
      </section>
    );
  }

  if (loading) {
    return (
      <section className="container" style={{ padding: '60px 24px', maxWidth: 900 }}>
        <div className="sidebar-card">Loading intelligence briefing…</div>
      </section>
    );
  }

  if (error || !article) {
    return (
      <section className="container" style={{ padding: '60px 24px', maxWidth: 900 }}>
        <div className="sidebar-card" style={{ borderLeft: '4px solid #dc2626' }}>
          <h2 style={{ marginTop: 0 }}>Unable to load briefing</h2>
          <p className="small-muted">{error || 'Article could not be found.'}</p>
          <div style={{ marginTop: 16 }}>
            <button className="btn-ghost" onClick={() => router.back()}>
              ← Go back
            </button>
            <Link className="btn-primary" href="/dashboard" style={{ marginLeft: 12 }}>
              Open live desk
            </Link>
          </div>
        </div>
      </section>
    );
  }

  const { title, description, source, image_url, image, link, published_at, fetched_at } = article;
  const heroImage = image_url || image || 'https://placehold.co/1200x600/0f172a/ffffff?text=AI-CTI';

  return (
    <section className="container" style={{ padding: '48px 24px', maxWidth: 960 }}>
      <article style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <div className="sidebar-card" style={{ overflow: 'hidden', padding: 0 }}>
          <div style={{ position: 'relative', width: '100%', paddingTop: '50%', background: '#0f172a' }}>
            <img
              src={heroImage}
              alt={title}
              style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }}
              onError={(event) => {
                event.currentTarget.src = 'https://placehold.co/1200x600/0f172a/ffffff?text=AI-CTI';
              }}
            />
          </div>
          <div style={{ padding: '28px 28px 32px', display: 'grid', gap: 18 }}>
            <div style={{ textTransform: 'uppercase', fontSize: '0.75rem', letterSpacing: '0.32em', color: '#64748b', fontWeight: 600 }}>
              {source || 'Unknown source'}
            </div>
            <h1 className="h1" style={{ fontSize: '2rem', marginBottom: 4 }}>{title}</h1>
            <p className="small-muted" style={{ margin: 0 }}>{description}</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, fontSize: '0.9rem', color: '#475569' }}>
              <span>Published: {formatTimestamp(published_at || fetched_at)}</span>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
              <a className="btn-primary" href={link} target="_blank" rel="noreferrer">
                Read original article
              </a>
              <Link className="btn-ghost" href="/dashboard">
                ← Back to live desk
              </Link>
            </div>
          </div>
        </div>

        {relatedItems.length > 0 && (
          <section className="sidebar-card" style={{ display: 'grid', gap: 18 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Related intelligence</h2>
              <Link className="btn-ghost" href="/intel">
                View intel dashboard →
              </Link>
            </div>
            <div style={{ display: 'grid', gap: 12 }}>
              {relatedItems.map((item) => (
                <div key={item.link} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <Link className="small-muted" href={`/story?link=${encodeURIComponent(item.link)}`}>
                    {item.title}
                  </Link>
                  <span style={{ color: '#94a3b8', fontSize: '0.8rem' }}>{formatTimestamp(item.published_at || item.fetched_at)}</span>
                </div>
              ))}
            </div>
          </section>
        )}
      </article>
    </section>
  );
}

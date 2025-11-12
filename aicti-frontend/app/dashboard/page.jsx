'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import ArticleCard from '../../components/ArticleCard';
import RightSidebar from '../../components/ui/RightSidebar';
import Ticker from '../../components/ui/Ticker';

const POLL_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

export default function Dashboard() {
  const [data, setData] = useState({ feeds: [], iocs: [], clusters: {} });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(
    async ({ silent = false } = {}) => {
      if (!silent) setLoading(true);
      try {
        setError(null);
        const res = await fetch('/api/results');
        if (!res.ok) {
          throw new Error(`API returned ${res.status}`);
        }
        const json = await res.json();
        console.log('[dashboard] Loaded data:', {
          feedsCount: json?.feeds?.length || 0,
          firstFeed: json?.feeds?.[0],
        });
        setData(json);
      } catch (err) {
        console.error('[dashboard] load error', err);
        setError(err.message || 'Failed to load data.');
      } finally {
        if (!silent) setLoading(false);
      }
    },
    []
  );

  const fetchLatest = useCallback(async () => {
    setLoading(true);
    try {
      const BACKEND = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
      const res = await fetch(`${BACKEND}/fetch_live`, { method: 'POST' });
      if (!res.ok) {
        throw new Error('Fetch trigger failed');
      }
      setTimeout(() => load({ silent: true }), 2000);
    } catch (err) {
      console.error('[dashboard] fetchLatest error', err);
      setError(err.message || 'Failed to trigger live ingestion.');
    } finally {
      setLoading(false);
    }
  }, [load]);

  useEffect(() => {
    load();
    const interval = setInterval(() => load({ silent: true }), POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [load]);

  const feeds = useMemo(() => {
    if (data?.feeds?.length) return data.feeds;
    return (data?.iocs || []).map((item) => ({
      title: item.title || item.value || item.file || '',
      link: item.link || '#',
      description: item.value || '',
      source: item.type || 'Unknown',
      fetched_at: item.created_at || null,
    }));
  }, [data]);

  const headlineCount = feeds.length;
  const distinctSources = new Set(feeds.map((item) => item.source)).size;
  const lastUpdated =
    feeds?.[0]?.fetched_at || feeds?.[0]?.published_at || data?.generated_at;

  return (
    <>
      <Ticker />
      <main className="container" style={{ paddingTop: 24, paddingBottom: 32 }}>
        <section className="sidebar-card" style={{ marginBottom: 20 }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: 16,
              flexWrap: 'wrap',
            }}
          >
            <div>
              <h1 className="h1">Daily Cyber Threat Intelligence Briefing</h1>
              <p className="small-muted">
                Live coverage curated from trusted security desks. Feed refreshes automatically every five minutes.
              </p>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              <button onClick={fetchLatest} className="btn-primary" disabled={loading}>
                {loading ? 'Fetching…' : 'Fetch Latest Batch'}
              </button>
              <button onClick={() => load()} className="btn-ghost" disabled={loading}>
                Manual Refresh
              </button>
            </div>
          </div>
          <div style={{ marginTop: 16, display: 'flex', flexWrap: 'wrap', gap: 16 }}>
            <StatPill label="Active headlines" value={headlineCount} />
            <StatPill label="Distinct sources" value={distinctSources} />
            <StatPill
              label="Last updated"
              value={
                lastUpdated ? new Date(lastUpdated).toLocaleString() : 'Not yet available'
              }
            />
          </div>
        </section>

        {error ? (
          <div
            className="sidebar-card"
            style={{ marginBottom: 20, borderLeft: '4px solid #dc2626' }}
          >
            <p style={{ color: '#dc2626', fontWeight: 600 }}>{error}</p>
          </div>
        ) : null}

        <div className="page-grid">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            {feeds.length === 0 ? (
              <div className="sidebar-card" style={{ textAlign: 'center' }}>
                No live intelligence yet. Trigger a fetch to populate the desk.
              </div>
            ) : (
              feeds.map((item) => <ArticleCard key={item.link} item={item} />)
            )}
          </div>
          <RightSidebar data={data} />
        </div>
      </main>
    </>
  );
}

function StatPill({ label, value }) {
  return (
    <div
      style={{
        minWidth: 160,
        background: '#f1f5f9',
        borderRadius: 12,
        padding: '12px 16px',
      }}
    >
      <div
        style={{
          fontSize: '0.75rem',
          fontWeight: 600,
          color: '#64748b',
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
        }}
      >
        {label}
      </div>
      <div style={{ marginTop: 6, fontSize: '1.1rem', fontWeight: 700, color: '#0f172a' }}>
        {value || '—'}
      </div>
    </div>
  );
}

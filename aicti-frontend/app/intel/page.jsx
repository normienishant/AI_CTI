'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';

function groupBySource(feeds = []) {
  const bucket = new Map();
  feeds.forEach((item) => {
    const key = (item?.source || 'Unknown').toLowerCase();
    bucket.set(key, (bucket.get(key) || 0) + 1);
  });
  return Array.from(bucket.entries())
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 8);
}

function groupByDate(feeds = []) {
  const bucket = new Map();
  feeds.forEach((item) => {
    const dateKey = new Date(item?.published_at || item?.fetched_at || Date.now())
      .toISOString()
      .slice(0, 10);
    bucket.set(dateKey, (bucket.get(dateKey) || 0) + 1);
  });
  return Array.from(bucket.entries())
    .map(([date, count]) => ({ date, count }))
    .sort((a, b) => (a.date > b.date ? -1 : 1))
    .slice(0, 10);
}

function calcIocHeatmap(iocs = []) {
  const bucket = new Map();
  iocs.forEach((ioc) => {
    const key = (ioc?.type || 'other').toLowerCase();
    bucket.set(key, (bucket.get(key) || 0) + 1);
  });
  return ['domain', 'ip', 'cve', 'hash'].map((name) => ({
    name,
    count: bucket.get(name) || 0,
  }));
}

export default function IntelDesk() {
  const [data, setData] = useState({ feeds: [], iocs: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        setLoading(true);
        const res = await fetch('/api/results');
        if (!res.ok) throw new Error(`API returned ${res.status}`);
        const json = await res.json();
        if (!cancelled) {
          setData(json);
        }
      } catch (err) {
        if (!cancelled) setError(err.message || 'Failed to pull intel data.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    const timer = setInterval(load, 5 * 60 * 1000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  const totalHeadlines = data?.feeds?.length || 0;
  const uniqueSources = useMemo(
    () => new Set((data.feeds || []).map((item) => item?.source)).size,
    [data.feeds]
  );
  const topSources = useMemo(() => groupBySource(data.feeds), [data.feeds]);
  const timeline = useMemo(() => groupByDate(data.feeds), [data.feeds]);
  const iocHeatmap = useMemo(() => calcIocHeatmap(data.iocs), [data.iocs]);

  return (
    <section className="container" style={{ padding: '48px 24px', display: 'grid', gap: 24 }}>
      <header style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <span className="small-muted" style={{ textTransform: 'uppercase', letterSpacing: '0.28em' }}>
          Intel dashboard
        </span>
        <h1 className="h1" style={{ fontSize: '2.2rem' }}>Threat desk analytics</h1>
        <p className="small-muted" style={{ maxWidth: 720 }}>
          Monitor aggregated coverage, top sources, indicator volumes, and the recent timeline of incidents captured by
          the AI-CTI ingestion pipeline. Data auto-refreshes every five minutes.
        </p>
      </header>

      {error && (
        <div className="sidebar-card" style={{ borderLeft: '4px solid #dc2626' }}>
          <strong>Intel fetch failed:</strong> {error}
        </div>
      )}

      <div style={{ display: 'grid', gap: 18, gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
        <div className="sidebar-card" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span className="small-muted" style={{ textTransform: 'uppercase', letterSpacing: '0.18em' }}>Headlines</span>
          <span style={{ fontSize: '2rem', fontWeight: 700 }}>{loading ? '—' : totalHeadlines}</span>
          <p className="small-muted">Active articles in the current batch.</p>
        </div>
        <div className="sidebar-card" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span className="small-muted" style={{ textTransform: 'uppercase', letterSpacing: '0.18em' }}>Sources</span>
          <span style={{ fontSize: '2rem', fontWeight: 700 }}>{loading ? '—' : uniqueSources}</span>
          <p className="small-muted">Distinct intelligence desks feeding AI-CTI.</p>
        </div>
        <div className="sidebar-card" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span className="small-muted" style={{ textTransform: 'uppercase', letterSpacing: '0.18em' }}>IOC volume</span>
          <span style={{ fontSize: '2rem', fontWeight: 700 }}>{loading ? '—' : (data.iocs || []).length}</span>
          <p className="small-muted">Indicators extracted across the latest batch.</p>
        </div>
      </div>

      <div style={{ display: 'grid', gap: 18, gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 1fr)' }}>
        <section className="sidebar-card" style={{ display: 'grid', gap: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Threat activity timeline</h2>
            <Link className="btn-ghost" href="/dashboard">
              Live desk →
            </Link>
          </div>
          <div style={{ display: 'grid', gap: 10 }}>
            {timeline.length === 0 && <span className="small-muted">No events logged yet.</span>}
            {timeline.map((entry) => (
              <div key={entry.date} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ minWidth: 96, fontWeight: 600 }}>{entry.date}</div>
                <div style={{ flex: 1, height: 8, background: '#e2e8f0', borderRadius: 999 }}>
                  <div
                    style={{
                      width: `${Math.min(100, entry.count * 12)}%`,
                      background: '#2563eb',
                      height: '100%',
                      borderRadius: 999,
                    }}
                  />
                </div>
                <span style={{ minWidth: 24, textAlign: 'right', fontWeight: 600 }}>{entry.count}</span>
              </div>
            ))}
          </div>
        </section>

        <aside className="sidebar-card" style={{ display: 'grid', gap: 16 }}>
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>IOC breakdown</h2>
          <div style={{ display: 'grid', gap: 12 }}>
            {iocHeatmap.map((item) => (
              <div key={item.name} style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ textTransform: 'uppercase', letterSpacing: '0.1em', fontSize: '0.75rem', color: '#64748b' }}>
                  {item.name}
                </span>
                <span style={{ fontWeight: 600 }}>{item.count}</span>
              </div>
            ))}
          </div>
        </aside>
      </div>

      <section className="sidebar-card" style={{ display: 'grid', gap: 16 }}>
        <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Top sources</h2>
        <div style={{ display: 'grid', gap: 12 }}>
          {topSources.length === 0 && <span className="small-muted">No feeds captured yet.</span>}
          {topSources.map((item) => (
            <div key={item.name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 600 }}>{item.name}</span>
              <span style={{ background: '#f1f5f9', padding: '4px 10px', borderRadius: 999, fontSize: '0.8rem' }}>
                {item.count}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section className="sidebar-card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <h2 style={{ margin: 0, fontSize: '1.05rem' }}>Need deeper coverage?</h2>
        <p className="small-muted" style={{ marginBottom: 0 }}>
          Reach out for bespoke collections, analyst summaries, or to plug AI-CTI into your incident response stack.
        </p>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <a
            className="btn-primary"
            href="https://www.linkedin.com/in/normienishant/"
            target="_blank"
            rel="noreferrer"
          >
            Message on LinkedIn
          </a>
          <a className="btn-ghost" href="mailto:threatdesk@ai-cti.io">
            Email the desk
          </a>
        </div>
      </section>
    </section>
  );
}

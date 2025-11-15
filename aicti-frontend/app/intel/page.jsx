'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as AreaTooltip,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';

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

function buildHourlyTimeline(feeds = []) {
  const bucket = new Map();
  feeds.forEach((item) => {
    const date = new Date(item?.published_at || item?.fetched_at || Date.now());
    const isoHour = new Date(date.toISOString().slice(0, 13) + ':00:00Z');
    const key = isoHour.toISOString();
    bucket.set(key, (bucket.get(key) || 0) + 1);
  });

  return Array.from(bucket.entries())
    .map(([timestamp, count]) => {
      const date = new Date(timestamp);
      return {
        timestamp,
        label: date.toLocaleTimeString('en', { hour: 'numeric', hour12: true }),
        count,
      };
    })
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
    .slice(-24);
}

function calcRiskBreakdown(feeds = []) {
  const bucket = { Critical: 0, High: 0, Medium: 0, Low: 0 };
  feeds.forEach((item) => {
    const level = item?.risk?.level;
    if (level && bucket[level] !== undefined) {
      bucket[level] += 1;
    }
  });
  return Object.entries(bucket).map(([level, count]) => ({ level, count }));
}

function calcSentimentGauge(feeds = []) {
  const bucket = { threat: 0, watch: 0 };
  feeds.forEach((item) => {
    const sentiment = item?.risk?.sentiment || 'watch';
    bucket[sentiment] = (bucket[sentiment] || 0) + 1;
  });
  return bucket;
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
  const timeline = useMemo(() => buildHourlyTimeline(data.feeds), [data.feeds]);
  const riskBreakdown = useMemo(() => calcRiskBreakdown(data.feeds), [data.feeds]);
  const sentimentGauge = useMemo(() => calcSentimentGauge(data.feeds), [data.feeds]);
  const threatCount = sentimentGauge?.threat ?? 0;
  const watchCount = sentimentGauge?.watch ?? 0;
  const iocHeatmap = useMemo(() => calcIocHeatmap(data.iocs), [data.iocs]);

  return (
    <section className="container" style={{ padding: '48px 24px', display: 'grid', gap: 24 }}>
      <header style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <span className="small-muted" style={{ textTransform: 'uppercase', letterSpacing: '0.28em' }}>
          Intel dashboard
        </span>
        <h1 className="h1" style={{ fontSize: '2.2rem', color: 'var(--text-default)' }}>Threat desk analytics</h1>
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
          <span style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--text-default)' }}>{loading ? '—' : totalHeadlines}</span>
          <p className="small-muted">Active articles in the current batch.</p>
        </div>
        <div className="sidebar-card" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span className="small-muted" style={{ textTransform: 'uppercase', letterSpacing: '0.18em' }}>Sources</span>
          <span style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--text-default)' }}>{loading ? '—' : uniqueSources}</span>
          <p className="small-muted">Distinct intelligence desks feeding AI-CTI.</p>
        </div>
        <div className="sidebar-card" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span className="small-muted" style={{ textTransform: 'uppercase', letterSpacing: '0.18em' }}>IOC volume</span>
          <span style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--text-default)' }}>{loading ? '—' : (data.iocs || []).length}</span>
          <p className="small-muted">Indicators extracted across the latest batch.</p>
        </div>
      </div>

      <div style={{ display: 'grid', gap: 18, gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 1fr)' }}>
        <section className="sidebar-card" style={{ display: 'grid', gap: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--text-default)' }}>Threat activity (last 24 hours)</h2>
            <Link className="btn-ghost" href="/dashboard">
              Live desk →
            </Link>
          </div>
          <div style={{ height: 260 }}>
            {timeline.length === 0 ? (
              <span className="small-muted">No events logged yet.</span>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={timeline} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="timelineGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#2563eb" stopOpacity={0.8} />
                      <stop offset="95%" stopColor="#2563eb" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.25)" />
                  <XAxis dataKey="label" stroke="var(--text-muted)" />
                  <YAxis allowDecimals={false} stroke="var(--text-muted)" />
                  <AreaTooltip
                    contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-soft)' }}
                    labelStyle={{ color: 'var(--text-muted)' }}
                    formatter={(value) => [`${value} headlines`, 'Activity']}
                  />
                  <Area type="monotone" dataKey="count" stroke="#2563eb" fill="url(#timelineGradient)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </section>

        <aside className="sidebar-card" style={{ display: 'grid', gap: 16 }}>
          <h2 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--text-default)' }}>IOC breakdown</h2>
          <div style={{ display: 'grid', gap: 12 }}>
            {iocHeatmap.map((item) => (
              <div key={item.name} style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ textTransform: 'uppercase', letterSpacing: '0.1em', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  {item.name}
                </span>
                <span style={{ fontWeight: 600, color: 'var(--text-default)' }}>{item.count}</span>
              </div>
            ))}
          </div>
        </aside>
      </div>

      <div style={{ display: 'grid', gap: 18, gridTemplateColumns: 'minmax(0, 1.5fr) minmax(0, 1fr)' }}>
        <section className="sidebar-card" style={{ display: 'grid', gap: 16 }}>
          <h2 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--text-default)' }}>Risk distribution</h2>
          <div style={{ height: 240 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={riskBreakdown} margin={{ top: 12, right: 20, left: 0, bottom: 12 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.25)" />
                <XAxis dataKey="level" stroke="var(--text-muted)" />
                <YAxis allowDecimals={false} stroke="var(--text-muted)" />
                <AreaTooltip
                  contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-soft)' }}
                  formatter={(value) => [`${value} headlines`, 'Risk']} />
                <Bar dataKey="count" radius={[8, 8, 0, 0]} fill="#f97316" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        <section className="sidebar-card" style={{ display: 'grid', gap: 12 }}>
          <h2 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--text-default)' }}>Sentiment snapshot</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600 }}>
              <span style={{ color: 'var(--text-default)' }}>Threat alerts</span>
              <span style={{ color: 'var(--text-default)' }}>{threatCount}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600 }}>
              <span style={{ color: 'var(--text-default)' }}>Watch advisories</span>
              <span style={{ color: 'var(--text-default)' }}>{watchCount}</span>
            </div>
            <div className="small-muted">
              Derived from heuristic risk scoring applied during ingestion.
            </div>
          </div>
        </section>
      </div>

      <div style={{ display: 'grid', gap: 18, gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)' }}>
        <section className="sidebar-card" style={{ display: 'grid', gap: 16 }}>
          <h2 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--text-default)' }}>Source distribution</h2>
          <div style={{ height: 280 }}>
            {topSources.length === 0 ? (
              <span className="small-muted">No feeds captured yet.</span>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={topSources}
                    dataKey="count"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                    labelLine={false}
                  >
                    {topSources.map((entry, index) => {
                      const colors = ['#2563eb', '#f97316', '#10b981', '#8b5cf6', '#ec4899', '#06b6d4', '#f59e0b', '#ef4444'];
                      return <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />;
                    })}
                  </Pie>
                  <AreaTooltip
                    contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-soft)' }}
                    formatter={(value) => [`${value} articles`, 'Count']}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </section>

        <section className="sidebar-card" style={{ display: 'grid', gap: 16 }}>
          <h2 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--text-default)' }}>IOC type breakdown</h2>
          <div style={{ height: 280 }}>
            {iocHeatmap.filter((item) => item.count > 0).length === 0 ? (
              <span className="small-muted">No IOCs extracted yet.</span>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={iocHeatmap.filter((item) => item.count > 0)} layout="vertical" margin={{ top: 12, right: 20, left: 0, bottom: 12 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.25)" />
                  <XAxis type="number" stroke="var(--text-muted)" />
                  <YAxis dataKey="name" type="category" stroke="var(--text-muted)" width={80} />
                  <AreaTooltip
                    contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-soft)' }}
                    formatter={(value) => [`${value} indicators`, 'Count']}
                  />
                  <Bar dataKey="count" radius={[0, 8, 8, 0]} fill="#10b981" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </section>
      </div>

      <section className="sidebar-card" style={{ display: 'grid', gap: 16 }}>
        <h2 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--text-default)' }}>Top sources</h2>
        <div style={{ display: 'grid', gap: 12 }}>
          {topSources.length === 0 && <span className="small-muted">No feeds captured yet.</span>}
          {topSources.map((item) => (
            <div key={item.name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 600, color: 'var(--text-default)' }}>{item.name}</span>
              <span style={{ background: 'var(--accent-soft)', color: 'var(--accent)', padding: '4px 10px', borderRadius: 999, fontSize: '0.8rem', fontWeight: 600 }}>
                {item.count}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section className="sidebar-card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <h2 style={{ margin: 0, fontSize: '1.05rem', color: 'var(--text-default)' }}>Need deeper coverage?</h2>
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
          <a className="btn-ghost" href="mailto:nishantiguess@gmail.com">
            Email the desk
          </a>
        </div>
      </section>
    </section>
  );
}

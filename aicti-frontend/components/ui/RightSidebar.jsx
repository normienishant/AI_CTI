'use client';

import React, { useMemo } from 'react';
import Link from 'next/link';
import { useSavedBriefings } from '../saved/SavedBriefingsProvider';

const STOP_WORDS = new Set([
  'the',
  'with',
  'from',
  'about',
  'alert',
  'report',
  'attack',
  'after',
  'over',
  'under',
  'their',
  'will',
  'could',
  'into',
  'users',
  'cyber',
  'security',
  'threat',
  'news',
]);

function formatTimestamp(value) {
  if (!value) return 'Unknown';
  try {
    return new Intl.DateTimeFormat('en', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function buildTopicList(feeds = []) {
  const counts = new Map();
  feeds.forEach((item) => {
    const text = [item?.title, item?.description].join(' ').toLowerCase();
    text
      .replace(/[^a-z0-9\s]/gi, ' ')
      .split(/\s+/)
      .filter((token) => token.length > 5 && !STOP_WORDS.has(token))
      .forEach((token) => {
        counts.set(token, (counts.get(token) || 0) + 1);
      });
  });
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);
}

function summariseIocs(iocs = []) {
  return iocs.reduce(
    (acc, item) => {
      const key = item?.type?.toLowerCase();
      if (!key) return acc;
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    },
    { ip: 0, domain: 0, cve: 0 }
  );
}

function extractHighRiskHeadlines(feeds = []) {
  return feeds
    .filter((item) => {
      const level = item?.risk?.level;
      return level === 'Critical' || level === 'High';
    })
    .slice(0, 4);
}

function formatEnrichment(enrichment) {
  if (!enrichment) return '';
  const { severity, context = [] } = enrichment;
  const ctx = context.slice(0, 1).join(' • ');
  return `${severity}${ctx ? ` • ${ctx}` : ''}`;
}

export default function RightSidebar({ data }) {
  const feeds = data?.feeds || [];
  const lastUpdated =
    feeds?.[0]?.fetched_at || feeds?.[0]?.published_at || data?.generated_at;
  const topics = useMemo(() => buildTopicList(feeds), [feeds]);
  const iocSummary = useMemo(() => summariseIocs(data?.iocs), [data?.iocs]);
  const highRisk = useMemo(() => extractHighRiskHeadlines(feeds), [feeds]);
  const enrichedIocs = useMemo(() => (data?.iocs || []).slice(0, 5), [data?.iocs]);
  const { saved } = useSavedBriefings();
  const savedBriefings = saved.slice(0, 4);

  return (
    <aside style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <section className="sidebar-card">
        <div style={{ fontWeight: 700, marginBottom: 6, color: 'var(--text-default)' }}>Desk status</div>
        <p className="small-muted" style={{ marginBottom: 12 }}>
          Last synced: {formatTimestamp(lastUpdated)}
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', fontWeight: 600 }}>
            <span>Active headlines</span>
            <span>{feeds.length}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', fontWeight: 600 }}>
            <span>IPs flagged</span>
            <span>{iocSummary.ip}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', fontWeight: 600 }}>
            <span>Domains observed</span>
            <span>{iocSummary.domain}</span>
          </div>
        </div>
        <div style={{ marginTop: 14 }}>
          <a className="btn-ghost" href="/intel">
            Open intel dashboard →
          </a>
        </div>
      </section>

      <section className="sidebar-card">
        <div style={{ fontWeight: 700, marginBottom: 6, color: 'var(--text-default)' }}>Trending topics</div>
        {topics.length === 0 ? (
          <p className="small-muted">No live topics detected yet.</p>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {topics.map(([topic, count]) => (
              <li key={topic} style={{ fontSize: '0.85rem', fontWeight: 600, display: 'flex', justifyContent: 'space-between' }}>
                <span>#{topic}</span>
                <span style={{ color: '#64748b' }}>{count}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="sidebar-card">
        <div style={{ fontWeight: 700, marginBottom: 6, color: 'var(--text-default)' }}>High-risk headlines</div>
        {highRisk.length === 0 ? (
          <p className="small-muted">No critical alerts in this batch.</p>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {highRisk.map((item) => (
              <li key={item.link} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <span style={{ fontWeight: 600, color: 'var(--text-default)' }}>{item.title}</span>
                <span style={{ fontSize: '0.78rem', color: '#ef4444', fontWeight: 600 }}>
                  {item?.risk?.level} • {item?.risk?.sentiment}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="sidebar-card">
        <div style={{ fontWeight: 700, marginBottom: 6, color: 'var(--text-default)' }}>Latest indicators</div>
        {enrichedIocs.length === 0 ? (
          <p className="small-muted">No indicators extracted yet.</p>
        ) : (
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 10 }}>
            {enrichedIocs.map((ioc, idx) => (
              <li key={`${ioc.value}-${idx}`} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                  {ioc.type}
                </span>
                <span style={{ fontWeight: 600, color: 'var(--text-default)' }}>{ioc.value}</span>
                <span style={{ fontSize: '0.78rem', color: '#f97316' }}>{formatEnrichment(ioc.enrichment)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="sidebar-card">
        <div style={{ fontWeight: 700, marginBottom: 6, color: 'var(--text-default)' }}>Saved briefings</div>
        {savedBriefings.length === 0 ? (
          <p className="small-muted">Use the bookmark icon on any headline to curate your personal list.</p>
        ) : (
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 10 }}>
            {savedBriefings.map((item) => (
              <li key={item.link} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <Link href={`/story?link=${encodeURIComponent(item.link)}`} className="small-muted" style={{ fontWeight: 600 }}>
                  {item.title || item.link}
                </Link>
                <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                  {item.source} • {item.risk_level || 'Unknown risk'}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="sidebar-card" style={{ textAlign: 'center' }}>
        <div className="small-muted" style={{ marginBottom: 8 }}>
          Stay ahead of adversaries
        </div>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-default)', marginBottom: 12 }}>
          Subscribe to the analyst brief for weekly summaries and IOC dumps.
        </p>
        <a
          href="https://www.linkedin.com/in/designsbynishant"
          className="btn-primary"
          style={{ justifyContent: 'center' }}
          target="_blank"
          rel="noreferrer"
        >
          Message on LinkedIn
        </a>
      </section>
    </aside>
  );
}

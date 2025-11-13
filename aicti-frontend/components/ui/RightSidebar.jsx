import React, { useMemo } from 'react';

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

export default function RightSidebar({ data }) {
  const feeds = data?.feeds || [];
  const lastUpdated =
    feeds?.[0]?.fetched_at || feeds?.[0]?.published_at || data?.generated_at;
  const topics = useMemo(() => buildTopicList(feeds), [feeds]);
  const iocSummary = useMemo(() => summariseIocs(data?.iocs), [data?.iocs]);

  return (
    <aside style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <section className="sidebar-card">
        <div style={{ fontWeight: 700, marginBottom: 6 }}>Desk status</div>
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
        <div style={{ fontWeight: 700, marginBottom: 6 }}>Trending topics</div>
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

      <section className="sidebar-card" style={{ textAlign: 'center' }}>
        <div className="small-muted" style={{ marginBottom: 8 }}>
          Stay ahead of adversaries
        </div>
        <p style={{ fontSize: '0.85rem', color: '#1f2937', marginBottom: 12 }}>
          Subscribe to the analyst brief for weekly summaries and IOC dumps.
        </p>
        <a
          href="https://www.linkedin.com/in/normienishant/messages/"
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

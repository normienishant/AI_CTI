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
  const [lastRefreshedAt, setLastRefreshedAt] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSource, setSelectedSource] = useState('all');

  const load = useCallback(
    async ({ silent = false } = {}) => {
      if (!silent) setLoading(true);
      try {
        setError(null);
        const res = await fetch(`/api/results?t=${Date.now()}`, {
          cache: 'no-store',
          headers: {
            'Cache-Control': 'no-cache',
          },
        });
        if (!res.ok) {
          throw new Error(`API returned ${res.status}`);
        }
        const json = await res.json();
        if (json.error) {
          setError(json.error);
        }
        // Debug: Log image URLs in received data
        console.log('[Dashboard] Received feeds:', json.feeds?.length || 0);
        if (json.feeds && json.feeds.length > 0) {
          const withImages = json.feeds.filter(f => f.image_url || f.image).length;
          console.log('[Dashboard] Feeds with images:', withImages, '/', json.feeds.length);
          // Log first 3 articles' image data
          json.feeds.slice(0, 3).forEach((feed, idx) => {
            console.log(`[Dashboard] Article ${idx + 1}:`, {
              title: feed.title?.substring(0, 50),
              image_url: feed.image_url || 'MISSING',
              image: feed.image || 'MISSING',
            });
          });
        }
        setData(json);
        setLastRefreshedAt(new Date().toISOString());
      } catch (err) {
        console.error('[dashboard] load error', err);
        const errorMsg = err.message || 'Failed to load data.';
        setError(errorMsg);
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
    let allFeeds = [];
    if (data?.feeds?.length) {
      allFeeds = data.feeds;
    } else {
      allFeeds = (data?.iocs || []).map((item) => ({
        title: item.title || item.value || item.file || '',
        link: item.link || '#',
        description: item.value || '',
        source: item.type || 'Unknown',
        fetched_at: item.created_at || null,
      }));
    }

    allFeeds.sort((a, b) => {
      const dateA = a.published_at || a.fetched_at || '';
      const dateB = b.published_at || b.fetched_at || '';
      if (!dateA && !dateB) return 0;
      if (!dateA) return 1;
      if (!dateB) return -1;
      return new Date(dateB).getTime() - new Date(dateA).getTime();
    });

    return allFeeds;
  }, [data]);

  const availableSources = useMemo(() => {
    const set = new Set(feeds.map((item) => (item.source || 'Unknown').trim()));
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [feeds]);

  const filteredFeeds = useMemo(() => {
    const term = searchQuery.trim().toLowerCase();
    return feeds.filter((item) => {
      const matchesSource =
        selectedSource === 'all' || (item.source || '').toLowerCase() === selectedSource;
      if (!matchesSource) return false;
      if (!term) return true;
      const haystack = [item.title, item.description, item.source]
        .join(' ')
        .toLowerCase();
      return haystack.includes(term);
    });
  }, [feeds, searchQuery, selectedSource]);

  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 6;

  const totalPages = Math.ceil(filteredFeeds.length / itemsPerPage) || 1;
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const currentFeeds = filteredFeeds.slice(startIndex, endIndex);

  useEffect(() => {
    setCurrentPage(1);
  }, [filteredFeeds.length, selectedSource, searchQuery]);

  const headlineCount = feeds.length;
  const distinctSources = availableSources.length;
  const lastUpdated =
    currentFeeds?.[0]?.fetched_at || currentFeeds?.[0]?.published_at || data?.generated_at;

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
              <h1 className="h1" style={{ color: 'var(--text-default)' }}>Daily Cyber Threat Intelligence Briefing</h1>
              <p className="small-muted">
                Live coverage curated from trusted security desks. Feed refreshes automatically every five minutes.
              </p>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end' }}>
              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                Last refreshed {lastRefreshedAt ? new Date(lastRefreshedAt).toLocaleTimeString() : '—'} · auto refresh every 5 min
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
          </div>

          <div style={{ marginTop: 20, display: 'flex', flexWrap: 'wrap', gap: 16 }}>
            <div style={{ display: 'flex', flex: '1 1 280px', gap: 10 }}>
              <div style={{ flex: 1 }}>
                <label className="small-muted" style={{ display: 'block', marginBottom: 6, color: 'var(--text-muted)' }}>
                  Filter by source
                </label>
                <select
                  value={selectedSource}
                  onChange={(event) => setSelectedSource(event.target.value.toLowerCase())}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: 10,
                    border: '1px solid var(--border-soft)',
                    background: 'var(--bg-card)',
                    color: 'var(--text-default)',
                  }}
                >
                  <option value="all">All sources</option>
                  {availableSources.map((source) => (
                    <option key={source} value={source.toLowerCase()}>
                      {source}
                    </option>
                  ))}
                </select>
              </div>
              <div style={{ flex: 1 }}>
                <label className="small-muted" style={{ display: 'block', marginBottom: 6, color: 'var(--text-muted)' }}>
                  Search headlines & summaries
                </label>
                <input
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  type="search"
                  placeholder="Try ransomware, zero-day, CVE…"
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: 10,
                    border: '1px solid var(--border-soft)',
                    background: 'var(--bg-card)',
                    color: 'var(--text-default)',
                  }}
                />
              </div>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
              <StatPill label="Active headlines" value={headlineCount} />
              <StatPill label="Distinct sources" value={distinctSources} />
              <StatPill
                label="Filtered view"
                value={`${filteredFeeds.length} items`}
              />
            </div>
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
            {loading && feeds.length === 0 ? (
              <>
                {Array.from({ length: 3 }).map((_, idx) => (
                  <SkeletonArticleCard key={`skeleton-${idx}`} />
                ))}
              </>
            ) : filteredFeeds.length === 0 ? (
              <div className="sidebar-card" style={{ textAlign: 'center', color: 'var(--text-default)' }}>
                No matching intelligence. Adjust filters or trigger a new fetch.
              </div>
            ) : (
              <>
                {currentFeeds.map((item) => (
                  <ArticleCard key={item.link} item={item} />
                ))}

                {totalPages > 1 && (
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'center',
                      alignItems: 'center',
                      gap: 12,
                      marginTop: 24,
                      padding: '16px 0',
                    }}
                  >
                    <button
                      onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                      disabled={currentPage === 1}
                      className="btn-ghost"
                      style={{
                        opacity: currentPage === 1 ? 0.5 : 1,
                        cursor: currentPage === 1 ? 'not-allowed' : 'pointer',
                      }}
                    >
                      ← Previous
                    </button>

                    <span
                      style={{
                        fontSize: '0.9rem',
                        fontWeight: 600,
                        color: 'var(--text-muted)',
                        minWidth: 120,
                        textAlign: 'center',
                      }}
                    >
                      Page {currentPage} of {totalPages}
                    </span>

                    <button
                      onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                      disabled={currentPage === totalPages}
                      className="btn-ghost"
                      style={{
                        opacity: currentPage === totalPages ? 0.5 : 1,
                        cursor: currentPage === totalPages ? 'not-allowed' : 'pointer',
                      }}
                    >
                      Next →
                    </button>
                  </div>
                )}
              </>
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
        background: 'var(--bg-card)',
        borderRadius: 12,
        padding: '12px 16px',
        border: '1px solid var(--border-soft)',
        color: 'var(--text-default)',
        boxShadow: 'var(--shadow-card)',
      }}
    >
      <div
        style={{
          fontSize: '0.75rem',
          fontWeight: 600,
          color: 'var(--text-muted)',
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
        }}
      >
        {label}
      </div>
      <div style={{ marginTop: 6, fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-default)' }}>
        {value || '—'}
      </div>
    </div>
  );
}

function SkeletonArticleCard() {
  return (
    <div
      className="article-card"
      style={{
        opacity: 0.6,
        pointerEvents: 'none',
        borderStyle: 'dashed',
      }}
    >
      <div
        className="article-thumb"
        style={{
          background: 'linear-gradient(135deg, rgba(148, 163, 184, 0.2), rgba(148, 163, 184, 0.08))',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <div className="pulse" style={{ width: '60%', height: '60%', borderRadius: 10 }} />
      </div>
      <div className="article-body" style={{ display: 'grid', gap: 10 }}>
        <div style={{ height: 14, background: 'rgba(148, 163, 184, 0.25)', borderRadius: 8 }} />
        <div style={{ height: 18, background: 'rgba(148, 163, 184, 0.2)', borderRadius: 8, width: '80%' }} />
        <div style={{ height: 60, background: 'rgba(148, 163, 184, 0.12)', borderRadius: 10 }} />
        <div style={{ display: 'flex', gap: 12 }}>
          <div style={{ height: 32, flex: 1, background: 'rgba(148, 163, 184, 0.2)', borderRadius: 8 }} />
          <div style={{ height: 32, flex: 1, background: 'rgba(148, 163, 184, 0.12)', borderRadius: 8 }} />
        </div>
      </div>
    </div>
  );
}

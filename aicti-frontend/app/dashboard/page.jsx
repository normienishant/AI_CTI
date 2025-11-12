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
        // Add cache-busting timestamp to prevent stale data
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
        console.log('[dashboard] Loaded data:', {
          feedsCount: json?.feeds?.length || 0,
          firstFeed: json?.feeds?.[0],
          error: json?.error,
        });
        
        // If there's an error in the response, show it
        if (json.error) {
          setError(json.error);
        }
        
        setData(json);
      } catch (err) {
        console.error('[dashboard] load error', err);
        // Check if error is in response
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
    
    // Sort by date: latest first (published_at or fetched_at)
    allFeeds.sort((a, b) => {
      const dateA = a.published_at || a.fetched_at || '';
      const dateB = b.published_at || b.fetched_at || '';
      if (!dateA && !dateB) return 0;
      if (!dateA) return 1; // A goes to end
      if (!dateB) return -1; // B goes to end
      return new Date(dateB).getTime() - new Date(dateA).getTime(); // Latest first
    });
    
    return allFeeds;
  }, [data]);
  
  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 6; // 5-6 items per page to match sidebar height
  
  // Calculate pagination
  const totalPages = Math.ceil(feeds.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const currentFeeds = feeds.slice(startIndex, endIndex);
  
  // Reset to page 1 when feeds change
  useEffect(() => {
    setCurrentPage(1);
  }, [feeds.length]);

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
              <>
                {currentFeeds.map((item) => (
                  <ArticleCard key={item.link} item={item} />
                ))}
                
                {/* Pagination Controls */}
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
                        color: '#64748b',
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

'use client';
import { useEffect, useState, useRef } from 'react';

export default function Ticker({ pollInterval = 30000 }) {
  const [items, setItems] = useState([]);
  const mounted = useRef(true);

  async function load() {
    try {
      const res = await fetch('/api/results');
      const json = await res.json();
      // Create simple headlines array from feeds or iocs
      let headlines = [];
      if (json.feeds && json.feeds.length) {
        headlines = json.feeds.map(f => ({
          title: f.title || f.link || 'Untitled',
          source: (f.source || (f.link && (new URL(f.link)).hostname) || 'unknown')
        }));
      } else if (json.iocs && json.iocs.length) {
        headlines = json.iocs.slice(0, 30).map(i => ({
          title: i.title || i.file || 'Untitled',
          source: (i.iocs?.domains?.[0] || 'unknown')
        }));
      }
      // fallback short example
      if (!headlines.length) {
        headlines = [
          { title: 'No news right now — click Fetch Latest', source: '' }
        ];
      }
      if (mounted.current) setItems(headlines);
    } catch (e) {
      if (mounted.current) setItems([{ title: 'Failed to load headlines', source: '' }]);
      console.error('Ticker load error', e);
    }
  }

  useEffect(() => {
    mounted.current = true;
    load();
    const t = setInterval(load, pollInterval);
    return () => { mounted.current = false; clearInterval(t); };
  }, [pollInterval]);

  // Build the long text to scroll: "source — title  •  source — title  • ..."
  const text = items.map(h => (h.source ? `${h.source} — ${h.title}` : h.title)).join('  •  ');

  return (
    <div className="ticker-wrapper" role="region" aria-label="Breaking news ticker">
      <div className="ticker-inner" tabIndex={0}>
        <div className="ticker-track">
          <span className="ticker-text">{text}&nbsp;&nbsp;&nbsp;&nbsp;</span>
          <span className="ticker-text">{text}&nbsp;&nbsp;&nbsp;&nbsp;</span>
        </div>
      </div>
    </div>
  );
}

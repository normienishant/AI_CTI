'use client';

import { useEffect, useState } from 'react';
import { X } from 'lucide-react';

const VERSION = '2025.11.13';
const STORAGE_KEY = 'ai_cti_whats_new_dismissed';

const CHANGELOG = [
  'Dark-mode aware UI polish with risk tagging and saved briefings.',
  'Live threat scoring, timeline analytics, and IOC enrichment.',
  'Story briefings with highlights, related feeds, and OG imagery.',
];

export default function WhatsNewBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored !== VERSION) {
      setVisible(true);
    }
  }, []);

  const dismiss = () => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, VERSION);
    }
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <aside
      className="sidebar-card"
      style={{
        borderLeft: '4px solid var(--accent)',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        position: 'relative',
      }}
    >
      <button
        type="button"
        onClick={dismiss}
        aria-label="Dismiss what's new"
        style={{
          position: 'absolute',
          top: 12,
          right: 12,
          border: 'none',
          background: 'transparent',
          cursor: 'pointer',
          color: 'var(--text-muted)',
        }}
      >
        <X size={16} />
      </button>
      <span className="small-muted" style={{ textTransform: 'uppercase', letterSpacing: '0.24em' }}>
        What’s new
      </span>
      <h2 style={{ margin: 0, fontSize: '1.1rem', color: 'var(--text-default)' }}>
        AI-CTI just got a major upgrade
      </h2>
      <ul style={{ margin: 0, paddingLeft: 18, color: 'var(--text-subtle)', fontSize: '0.9rem', display: 'grid', gap: 6 }}>
        {CHANGELOG.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </aside>
  );
}

'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

const STORAGE_KEY = 'ai_cti_client_id';
const SavedContext = createContext(undefined);

function ensureClientId() {
  if (typeof window === 'undefined') return null;
  let value = window.localStorage.getItem(STORAGE_KEY);
  if (!value) {
    value = window.crypto?.randomUUID?.() || Math.random().toString(36).slice(2);
    window.localStorage.setItem(STORAGE_KEY, value);
  }
  return value;
}

export default function SavedBriefingsProvider({ children }) {
  const [clientId, setClientId] = useState(null);
  const [saved, setSaved] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const id = ensureClientId();
    setClientId(id);
  }, []);

  const fetchSaved = useCallback(async () => {
    if (!clientId) return;
    try {
      setLoading(true);
      const res = await fetch(`/api/saved?clientId=${clientId}`, { cache: 'no-store' });
      const json = await res.json();
      if (json?.items) {
        setSaved(json.items);
      }
      setError(json?.error || null);
    } catch (err) {
      setError(err.message || 'Failed to load saved briefings.');
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    if (!clientId) return;
    fetchSaved();
  }, [clientId, fetchSaved]);

  const isSaved = useCallback(
    (link) => saved.some((item) => item.link === link),
    [saved]
  );

  const toggleSaved = useCallback(
    async (item) => {
      if (!clientId || !item?.link) return;
      const alreadySaved = isSaved(item.link);
      try {
        setError(null);
        if (alreadySaved) {
          await fetch(`/api/saved?clientId=${clientId}&link=${encodeURIComponent(item.link)}`, {
            method: 'DELETE',
          });
          setSaved((prev) => prev.filter((entry) => entry.link !== item.link));
        } else {
          const payload = {
            client_id: clientId,
            link: item.link,
            title: item.title || '',
            source: item.source || item.source_name || 'Unknown',
            image_url: item.image_url || item.image || '',
            risk_level: item?.risk?.level,
            risk_score: item?.risk?.score,
          };
          const res = await fetch('/api/saved', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
          });
          if (!res.ok) {
            throw new Error('Failed to save briefing');
          }
          const json = await res.json();
          if (json?.item) {
            setSaved((prev) => [json.item, ...prev.filter((entry) => entry.link !== json.item.link)].slice(0, 50));
          }
        }
      } catch (err) {
        setError(err.message || 'Failed to update saved briefing.');
      }
    },
    [clientId, isSaved]
  );

  const value = useMemo(
    () => ({ saved, loading, error, clientId, fetchSaved, toggleSaved, isSaved }),
    [saved, loading, error, clientId, fetchSaved, toggleSaved, isSaved]
  );

  return <SavedContext.Provider value={value}>{children}</SavedContext.Provider>;
}

export function useSavedBriefings() {
  const context = useContext(SavedContext);
  if (!context) {
    throw new Error('useSavedBriefings must be used within SavedBriefingsProvider');
  }
  return context;
}

'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

const STORAGE_KEY = 'ai_cti_client_id';
const SAVED_CACHE_KEY = 'ai_cti_saved_cache_v1';
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

  const persistSavedCache = useCallback((items) => {
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(SAVED_CACHE_KEY, JSON.stringify(items.slice(0, 50)));
    } catch (err) {
      console.warn('[saved] cache write failed', err);
    }
  }, []);

  const loadSavedCache = useCallback(() => {
    if (typeof window === 'undefined') return [];
    try {
      const raw = window.localStorage.getItem(SAVED_CACHE_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }, []);

  useEffect(() => {
    const id = ensureClientId();
    setClientId(id);

    const cached = loadSavedCache();
    if (cached.length) {
      setSaved(cached);
      setLoading(false);
    }
  }, [loadSavedCache]);

  const fetchSaved = useCallback(async () => {
    if (!clientId) return;
    try {
      setLoading(true);
      const res = await fetch(`/api/saved?clientId=${clientId}`, { cache: 'no-store' });
      const json = await res.json();
      if (json?.items) {
        setSaved(json.items);
        persistSavedCache(json.items);
      } else {
        const cached = loadSavedCache();
        if (cached.length) setSaved(cached);
      }
      setError(json?.error || null);
    } catch (err) {
      setError(err.message || 'Failed to load saved briefings.');
      const cached = loadSavedCache();
      if (cached.length) setSaved(cached);
    } finally {
      setLoading(false);
    }
  }, [clientId, loadSavedCache, persistSavedCache]);

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
      const previous = [...saved];
      try {
        setError(null);
        if (alreadySaved) {
          setSaved((prev) => {
            const next = prev.filter((entry) => entry.link !== item.link);
            persistSavedCache(next);
            return next;
          });
          await fetch(`/api/saved?clientId=${clientId}&link=${encodeURIComponent(item.link)}`, {
            method: 'DELETE',
          });
        } else {
          const payload = {
            client_id: clientId,
            link: item.link,
            title: item.title || '',
            source: item.source || item.source_name || 'Unknown',
            image_url: item.image_url || item.image || '',
            risk_level: item?.risk?.level,
            risk_score: item?.risk?.score,
            saved_at: new Date().toISOString(),
          };
          setSaved((prev) => {
            const optimistic = [payload, ...prev.filter((entry) => entry.link !== item.link)].slice(0, 50);
            persistSavedCache(optimistic);
            return optimistic;
          });
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
            setSaved((prev) => {
              const synced = [json.item, ...prev.filter((entry) => entry.link !== json.item.link)].slice(0, 50);
              persistSavedCache(synced);
              return synced;
            });
          }
        }
      } catch (err) {
        setError(err.message || 'Failed to update saved briefing.');
        setSaved(previous);
        persistSavedCache(previous);
      }
    },
    [clientId, isSaved, persistSavedCache, saved]
  );

  useEffect(() => {
    persistSavedCache(saved);
  }, [saved, persistSavedCache]);

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

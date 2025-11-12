// small helper to prettify filenames like live_feed_20251108_152800_0
export function humanizeTitle(raw) {
  if (!raw) return '';
  
  // If title is already a proper sentence/article title (has spaces, proper capitalization, length > 20 chars), return as-is
  if (raw.length > 20 && /\s/.test(raw) && !/^[a-z0-9_]+$/.test(raw)) {
    return raw.trim().replace(/\s{2,}/g, ' ');
  }
  
  // if looks like a filename (contains underscores and digits, no spaces), try to transform
  const fileLike = /^live_feed|^[a-z0-9_]+$|^[a-z0-9_-]+\d{4,}/i;
  if (fileLike.test(raw) && !/\s/.test(raw)) {
    // replace underscores and hyphens with space, remove multiple spaces
    const s = raw.replace(/[_\-]+/g, ' ')
                 .replace(/\s{2,}/g, ' ')
                 .trim();
    // capitalise sensible words but keep code-like digits intact
    return s.split(' ').map(w => {
      if (/\d+/.test(w)) return w;
      return w.charAt(0).toUpperCase() + w.slice(1);
    }).join(' ');
  }
  // fallback: trim & compress whitespace
  return raw.trim().replace(/\s{2,}/g, ' ');
}

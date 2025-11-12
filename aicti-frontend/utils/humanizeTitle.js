// small helper to prettify filenames like live_feed_20251108_152800_0
export function humanizeTitle(raw) {
  if (!raw) return '';
  // if looks like a filename (contains underscores and digits), try to transform
  const fileLike = /[_-]\d{4,}|^live_feed|^[a-z0-9_]+$/i;
  if (fileLike.test(raw)) {
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

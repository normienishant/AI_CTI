import { humanizeTitle } from '../utils/humanizeTitle';

const FALLBACK_IMAGE =
  'https://placehold.co/600x360/0f172a/ffffff?text=AI-CTI';

function formatHostname(source) {
  if (!source) return 'Unknown';
  try {
    // Decode URL encoding (e.g., %20 -> space, %2F -> /)
    let decoded = decodeURIComponent(source);
    // If it's a URL, extract hostname
    if (decoded.startsWith('http')) {
      const url = new URL(decoded);
      return url.hostname.replace(/^www\./, '');
    }
    // If it's already a hostname, clean it
    return decoded.replace(/^www\./, '').replace(/%20/g, ' ').replace(/%2F/g, '/');
  } catch {
    // If decoding fails, try basic cleaning
    return source.replace(/%20/g, ' ').replace(/%2F/g, '/').replace(/^www\./, '');
  }
}

function formatTimestamp(value) {
  if (!value) return '';
  try {
    return new Intl.DateTimeFormat('en', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(value));
  } catch {
    return value;
  }
}

export default function ArticleCard({ item }) {
  // Prioritize title from Supabase, only fallback to file/link if title is truly missing
  const titleRaw = item?.title || '';
  // Only use humanizeTitle if title looks like a filename, otherwise use as-is
  const title = titleRaw 
    ? (titleRaw.length > 20 && /\s/.test(titleRaw) 
        ? titleRaw.trim() 
        : humanizeTitle(titleRaw) || titleRaw)
    : (item?.file || item?.link || 'Untitled');
  const desc = item?.description || item?.summary || 'No description available.';
  const link = item?.link || item?.url || '#';
  const image = item?.image || item?.image_url || FALLBACK_IMAGE;
  const source = formatHostname(item?.source || item?.raw_source);
  const published = formatTimestamp(item?.published_at || item?.fetched_at);

  return (
    <article className="article-card">
      <div className="article-thumb">
        <img
          src={image || FALLBACK_IMAGE}
          alt={title}
          loading="lazy"
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          onError={(event) => {
            event.currentTarget.src = FALLBACK_IMAGE;
          }}
        />
      </div>
      <div className="article-body">
        <div className="article-meta">
          {source}
          {published ? ` • ${published}` : null}
        </div>
        <h3 className="article-title">{title}</h3>
        <p className="article-excerpt">{desc}</p>
        <div className="article-actions">
          <a href={link} target="_blank" rel="noreferrer" className="btn-ghost">
            Read original
          </a>
          <button
            type="button"
            className="btn-primary"
            onClick={() => window.open(link, '_blank', 'noopener')}
          >
            Open Source
          </button>
        </div>
      </div>
    </article>
  );
}

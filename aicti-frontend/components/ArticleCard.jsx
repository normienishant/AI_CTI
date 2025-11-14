import Link from 'next/link';
import { Bookmark, BookmarkCheck } from 'lucide-react';
import { humanizeTitle } from '../utils/humanizeTitle';
import RiskBadge from './ui/RiskBadge';
import { useSavedBriefings } from './saved/SavedBriefingsProvider';

const FALLBACK_IMAGE =
  'https://placehold.co/600x360/0f172a/ffffff?text=AI-CTI';

function extractHostname(item) {
  const link = item?.link || item?.url;
  if (!link) return null;
  try {
    return new URL(link).hostname.replace(/^www\./, '');
  } catch {
    return null;
  }
}

function stripHtml(value) {
  if (!value) return '';
  if (typeof value !== 'string') {
    return String(value);
  }
  return value
    .replace(/<[^>]*>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/\s+/g, ' ')
    .trim();
}

function pickImage(item) {
  const candidates = [
    item?.image_url,
    item?.image,
    item?.previewImage,
    item?.thumbnail,
  ];

  for (const candidate of candidates) {
    if (typeof candidate === 'string' && candidate.trim().length > 0) {
      return candidate.trim();
    }
  }

  const hostname = extractHostname(item);
  if (hostname) {
    return `https://logo.clearbit.com/${hostname}`;
  }

  return FALLBACK_IMAGE;
}

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
  const rawDesc = item?.description || item?.summary || '';
  const desc = stripHtml(rawDesc) || 'No description available.';
  const link = item?.link || item?.url || '#';
  const image = pickImage(item);
  const source = formatHostname(item?.source || item?.raw_source);
  const published = formatTimestamp(item?.published_at || item?.fetched_at);
  const risk = item?.risk;
  const tags = Array.isArray(item?.tags) ? item.tags.slice(0, 4) : [];

  // Debug logging for thumbnails
  if (process.env.NODE_ENV === 'development') {
    if (!item?.image_url && !item?.image) {
      console.log('[ArticleCard] No image_url for:', title.substring(0, 50), '| item keys:', Object.keys(item));
    } else if (image && image !== FALLBACK_IMAGE) {
      console.log('[ArticleCard] Using image:', image.substring(0, 80), 'for:', title.substring(0, 50));
    }
  }

  const { toggleSaved, isSaved } = useSavedBriefings();
  const isAlreadySaved = link !== '#' && isSaved(link);
  const handleToggleSaved = () => {
    toggleSaved({
      ...item,
      link,
      title,
      source,
      image_url: image,
    });
  };

  const encodedLink = link ? encodeURIComponent(link) : '';

  return (
    <article className="article-card">
      <div className="article-thumb">
        <img
          src={image || FALLBACK_IMAGE}
          alt={title}
          loading="lazy"
          style={{ 
            width: '100%', 
            height: '100%', 
            objectFit: 'cover',
            display: 'block',
            backgroundColor: 'var(--bg-card)'
          }}
          onError={(event) => {
            console.log('[ArticleCard] Image failed to load:', image);
            event.currentTarget.src = FALLBACK_IMAGE;
          }}
          onLoad={() => {
            if (image && image !== FALLBACK_IMAGE) {
              console.log('[ArticleCard] Image loaded successfully:', image.substring(0, 80));
            }
          }}
        />
      </div>
      <div className="article-body">
        <div className="article-meta">
          {source}
          {published ? ` • ${published}` : null}
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', margin: '6px 0' }}>
          <RiskBadge risk={risk} />
          {tags.map((tag) => (
            <span
              key={tag}
              style={{
                fontSize: '0.7rem',
                textTransform: 'uppercase',
                letterSpacing: '0.1em',
                background: 'var(--accent-soft)',
                color: 'var(--accent)',
                padding: '4px 8px',
                borderRadius: 999,
                fontWeight: 600,
              }}
            >
              {tag}
            </span>
          ))}
        </div>
        <h3 className="article-title">{title}</h3>
        <p className="article-excerpt">{desc}</p>
        <div className="article-actions">
          <button
            type="button"
            className="btn-ghost"
            onClick={handleToggleSaved}
            disabled={link === '#'}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
          >
            {isAlreadySaved ? <BookmarkCheck size={16} /> : <Bookmark size={16} />}
            {isAlreadySaved ? 'Saved' : 'Save'}
          </button>
          <Link className="btn-primary" href={`/story?link=${encodedLink}`}>
            View briefing
          </Link>
          <a href={link} target="_blank" rel="noreferrer" className="btn-ghost">
            Read original
          </a>
        </div>
      </div>
    </article>
  );
}

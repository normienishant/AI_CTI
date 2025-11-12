export default function FeedItem({title, source, desc, link, preview}) {
  return (
    <div className="card mb-3 feed-item-card flex flex-col sm:flex-row sm:justify-between sm:items-start gap-3">
      <div className="flex-1 min-w-0">
        <div style={{fontWeight:600, color: '#e6eef6', fontSize: '0.95rem', marginBottom: '4px'}} className="truncate">
          {title || 'Untitled'}
        </div>
        {source && (
          <div className="small-muted mb-1" style={{fontSize: '0.75rem'}}>
            {source}
          </div>
        )}
        {desc && (
          <div className="small-muted mt-1 line-clamp-2" style={{fontSize: '0.85rem'}}>
            {desc}
          </div>
        )}
        {preview && (
          <div className="small-muted mt-2 text-xs opacity-75 line-clamp-1">
            {preview}
          </div>
        )}
      </div>
      <div className="flex-shrink-0">
        <a 
          href={link || "#"} 
          target="_blank" 
          rel="noreferrer" 
          className="btn-primary"
          style={{padding: '8px 16px', fontSize: '0.875rem'}}
        >
          Open
        </a>
      </div>
    </div>
  );
}

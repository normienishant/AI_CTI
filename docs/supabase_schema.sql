-- Supabase schema for AI-CTI

-- Storage buckets (create via Supabase dashboard)
-- raw-feeds: stores raw JSON batches + article thumbnails

-- Articles table (unique on link)
create table if not exists public.articles (
  id bigserial primary key,
  title text,
  description text,
  link text unique,
  source text,
  source_name text,
  image_url text,
  published_at timestamptz,
  fetched_at timestamptz default timezone('utc', now())
);

create index if not exists idx_articles_published_at on public.articles (published_at desc nulls last);

-- IOCs table (lightweight indicator storage)
create table if not exists public.iocs (
  id bigserial primary key,
  file text,
  type text,
  value text,
  created_at timestamptz default timezone('utc', now())
);

create index if not exists idx_iocs_created_at on public.iocs (created_at desc nulls last);
create index if not exists idx_iocs_type on public.iocs (type);

-- Saved briefings table (user bookmarks)
create table if not exists public.saved_briefings (
  id bigserial primary key,
  client_id text not null,
  link text not null,
  title text,
  source text,
  image_url text,
  risk_level text,
  risk_score numeric,
  saved_at timestamptz default timezone('utc', now()),
  unique(client_id, link)
);

create index if not exists idx_saved_briefings_client_id on public.saved_briefings (client_id);
create index if not exists idx_saved_briefings_saved_at on public.saved_briefings (saved_at desc nulls last);


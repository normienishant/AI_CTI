# Saved Briefings Table Setup

## Problem
Console me 500 error aa raha hai kyunki `saved_briefings` table Supabase me exist nahi karti.

## Solution: Create Table in Supabase

### Step 1: Supabase Dashboard me jao
1. https://supabase.com pe login karo
2. Apne project pe click karo
3. Left sidebar me **SQL Editor** pe click karo

### Step 2: SQL Query Run Karo
SQL Editor me ye query paste karo aur **Run** button click karo:

```sql
-- Saved briefings table (user bookmarks)
CREATE TABLE IF NOT EXISTS public.saved_briefings (
  id BIGSERIAL PRIMARY KEY,
  client_id TEXT NOT NULL,
  link TEXT NOT NULL,
  title TEXT,
  source TEXT,
  image_url TEXT,
  risk_level TEXT,
  risk_score NUMERIC,
  saved_at TIMESTAMPTZ DEFAULT timezone('utc', now()),
  UNIQUE(client_id, link)
);

CREATE INDEX IF NOT EXISTS idx_saved_briefings_client_id 
  ON public.saved_briefings (client_id);

CREATE INDEX IF NOT EXISTS idx_saved_briefings_saved_at 
  ON public.saved_briefings (saved_at DESC NULLS LAST);
```

### Step 3: Verify
1. Left sidebar me **Table Editor** pe click karo
2. `saved_briefings` table dikhni chahiye
3. Columns check karo:
   - `id` (bigint, primary key)
   - `client_id` (text)
   - `link` (text)
   - `title` (text)
   - `source` (text)
   - `image_url` (text)
   - `risk_level` (text)
   - `risk_score` (numeric)
   - `saved_at` (timestamptz)

### Step 4: Test
1. Frontend me kisi article pe **Save** button click karo
2. Console me check karo - ab 500 error nahi aana chahiye
3. Backend logs me `[saved] ✓ Successfully saved briefing` dikhna chahiye
4. Right sidebar me "Saved briefings" section me article dikhna chahiye

## Important Notes

- **Unique Constraint**: `(client_id, link)` unique hai - same user same article ko do baar save nahi kar sakta
- **No RLS Needed**: Backend service role key use karta hai, so Row Level Security (RLS) enable karne ki zarurat nahi
- **Indexes**: Fast queries ke liye indexes add kiye gaye hain

## Troubleshooting

Agar table create karne ke baad bhi error aaye:

1. **Check Backend Logs**: Render.com pe backend logs check karo - `[saved]` messages dekho
2. **Verify Table Name**: Table name exactly `saved_briefings` hona chahiye (lowercase, underscore)
3. **Check Supabase Connection**: Backend me `SUPABASE_ENABLED` true hona chahiye
4. **Test Directly**: Supabase SQL Editor me manually insert karke test karo:
   ```sql
   INSERT INTO public.saved_briefings (client_id, link, title, source)
   VALUES ('test-client-123', 'https://example.com', 'Test Article', 'Test Source');
   ```


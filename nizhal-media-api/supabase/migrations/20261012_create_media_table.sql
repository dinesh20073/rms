-- ============================================================================
-- Migration: 20261012_create_media_table.sql
-- Description: Create public.media table for Nizhal Community Scrapbook
-- Environment: Supabase PostgreSQL
-- ============================================================================

-- 1. Ensure required extensions are available
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. Create public.media table
CREATE TABLE IF NOT EXISTS public.media (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'gathering',
    media_type TEXT NOT NULL CHECK (media_type IN ('image', 'video', 'link')),
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_published BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 3. Composite partial index for fast retrieval of published media ordered by sort_order and created_at
CREATE INDEX IF NOT EXISTS idx_media_published_sort_created 
ON public.media (sort_order ASC, created_at DESC) 
WHERE is_published = true;

-- Secondary index for category filtering if needed in future
CREATE INDEX IF NOT EXISTS idx_media_category 
ON public.media (category) 
WHERE is_published = true;

-- 4. Enable Row Level Security (RLS)
ALTER TABLE public.media ENABLE ROW LEVEL SECURITY;

-- 5. Public read policy: Allow anon and authenticated users to SELECT ONLY published records
DROP POLICY IF EXISTS "Allow public read access to published media" ON public.media;
CREATE POLICY "Allow public read access to published media" 
ON public.media 
FOR SELECT 
TO anon, authenticated 
USING (is_published = true);

-- 6. Write policies: Deny direct write access for anon & authenticated roles
-- (Inserts, updates, and deletes must occur exclusively via server-side service role key)
DROP POLICY IF EXISTS "Deny direct public write access" ON public.media;
CREATE POLICY "Deny direct public write access" 
ON public.media 
FOR ALL 
TO anon, authenticated 
USING (false) 
WITH CHECK (false);

-- ============================================================================
-- 7. Initial Seed Data (Optional sample memories for Nizhal Scrapbook)
-- ============================================================================
INSERT INTO public.media (title, description, url, category, media_type, sort_order, is_published)
VALUES 
(
    'Human. Stories. Connection.',
    'Listening deeply, no rush, just warmth ♡',
    'https://images.unsplash.com/photo-1529156069898-49953e39b3ac?auto=format&fit=crop&w=1200&q=80',
    'gathering',
    'image',
    1,
    true
),
(
    'Circle by the Sea',
    'Real conversations with good souls ✨',
    'https://images.unsplash.com/photo-1511632765486-a01980e01a18?auto=format&fit=crop&w=1200&q=80',
    'beach',
    'image',
    2,
    true
),
(
    'Campfire Reflections & Acoustic Notes',
    'Laughter echoing under starlit skies 🌿',
    'https://images.unsplash.com/photo-1478147427282-58a87a120781?auto=format&fit=crop&w=1200&q=80',
    'campfire',
    'image',
    3,
    true
)
ON CONFLICT DO NOTHING;

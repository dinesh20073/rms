import { createClient, SupabaseClient } from '@supabase/supabase-js';
import { Pool } from 'pg';
import { MediaRecord, PublicMediaItem } from './types';

let supabaseClientInstance: SupabaseClient | null = null;
let pgPoolInstance: Pool | null = null;

function getPgPool(): Pool | null {
  if (pgPoolInstance) return pgPoolInstance;
  const dbUrl = process.env.DATABASE_URL?.trim();
  if (!dbUrl) return null;

  pgPoolInstance = new Pool({
    connectionString: dbUrl,
    ssl: { rejectUnauthorized: false },
    max: 10,
    idleTimeoutMillis: 30000,
  });
  return pgPoolInstance;
}

export function getSupabaseAdminClient(): SupabaseClient | null {
  if (supabaseClientInstance) return supabaseClientInstance;

  const supabaseUrl = process.env.SUPABASE_URL?.trim();
  const supabaseServiceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY?.trim();

  if (!supabaseUrl || !supabaseServiceRoleKey) {
    return null;
  }

  supabaseClientInstance = createClient(supabaseUrl, supabaseServiceRoleKey, {
    auth: {
      persistSession: false,
      autoRefreshToken: false,
    },
  });

  return supabaseClientInstance;
}

/**
 * Retrieves all media records (including unpublished) for admin dashboard.
 */
export async function getAllMediaRecords(): Promise<MediaRecord[]> {
  const supabase = getSupabaseAdminClient();
  if (supabase) {
    const { data, error } = await supabase
      .from('media')
      .select('id, title, description, url, category, media_type, sort_order, is_published, created_at')
      .order('sort_order', { ascending: true })
      .order('created_at', { ascending: false });

    if (error) {
      throw new Error(`Supabase query error: ${error.message}`);
    }
    return (data || []) as MediaRecord[];
  }

  const pool = getPgPool();
  if (pool) {
    const query = `
      SELECT id, title, description, url, category, media_type, sort_order, is_published, created_at
      FROM public.media
      ORDER BY sort_order ASC, created_at DESC;
    `;
    const res = await pool.query(query);
    return res.rows.map((row) => ({
      id: row.id,
      title: row.title,
      description: row.description || '',
      url: row.url,
      category: row.category,
      media_type: row.media_type,
      sort_order: row.sort_order,
      is_published: row.is_published,
      created_at: row.created_at instanceof Date ? row.created_at.toISOString() : String(row.created_at),
    }));
  }

  throw new Error('Neither Supabase Service Role Key nor DATABASE_URL is configured');
}

/**
 * Retrieves all published media records from Supabase (via client or direct PostgreSQL pool).
 * Ordered by sort_order ASC, created_at DESC.
 */
export async function getPublishedMediaRecords(): Promise<PublicMediaItem[]> {
  const supabase = getSupabaseAdminClient();
  if (supabase) {
    const { data, error } = await supabase
      .from('media')
      .select('id, title, description, url, category, media_type, sort_order, created_at')
      .eq('is_published', true)
      .order('sort_order', { ascending: true })
      .order('created_at', { ascending: false });

    if (error) {
      throw new Error(`Supabase query error: ${error.message}`);
    }
    return (data || []) as PublicMediaItem[];
  }

  const pool = getPgPool();
  if (pool) {
    const query = `
      SELECT id, title, description, url, category, media_type, sort_order, created_at
      FROM public.media
      WHERE is_published = true
      ORDER BY sort_order ASC, created_at DESC;
    `;
    const res = await pool.query(query);
    return res.rows.map((row) => ({
      id: row.id,
      title: row.title,
      description: row.description || '',
      url: row.url,
      category: row.category,
      media_type: row.media_type,
      sort_order: row.sort_order,
      created_at: row.created_at instanceof Date ? row.created_at.toISOString() : String(row.created_at),
    }));
  }

  throw new Error('Neither Supabase Service Role Key nor DATABASE_URL is configured');
}

/**
 * Inserts a new media record into Supabase.
 */
export async function createMediaRecordInDb(item: {
  title: string;
  description: string;
  url: string;
  category: string;
  media_type: string;
  sort_order: number;
  is_published: boolean;
}): Promise<MediaRecord> {
  const supabase = getSupabaseAdminClient();
  if (supabase) {
    const { data, error } = await supabase
      .from('media')
      .insert([item])
      .select('id, title, description, url, category, media_type, sort_order, is_published, created_at')
      .single();

    if (error) {
      throw new Error(`Supabase insert error: ${error.message}`);
    }
    return data as MediaRecord;
  }

  const pool = getPgPool();
  if (pool) {
    const query = `
      INSERT INTO public.media (title, description, url, category, media_type, sort_order, is_published)
      VALUES ($1, $2, $3, $4, $5, $6, $7)
      RETURNING id, title, description, url, category, media_type, sort_order, is_published, created_at;
    `;
    const values = [
      item.title,
      item.description,
      item.url,
      item.category,
      item.media_type,
      item.sort_order,
      item.is_published,
    ];
    const res = await pool.query(query, values);
    const row = res.rows[0];
    return {
      id: row.id,
      title: row.title,
      description: row.description,
      url: row.url,
      category: row.category,
      media_type: row.media_type,
      sort_order: row.sort_order,
      is_published: row.is_published,
      created_at: row.created_at instanceof Date ? row.created_at.toISOString() : String(row.created_at),
    };
  }

  throw new Error('Neither Supabase Service Role Key nor DATABASE_URL is configured');
}

/**
 * Updates an existing media record.
 */
export async function updateMediaRecordInDb(id: string, updates: Partial<MediaRecord>): Promise<MediaRecord> {
  const supabase = getSupabaseAdminClient();
  if (supabase) {
    const { data, error } = await supabase
      .from('media')
      .update(updates)
      .eq('id', id)
      .select('id, title, description, url, category, media_type, sort_order, is_published, created_at')
      .single();

    if (error) throw new Error(error.message);
    return data as MediaRecord;
  }

  const pool = getPgPool();
  if (pool) {
    const fields: string[] = [];
    const values: any[] = [];
    let idx = 1;

    for (const [key, val] of Object.entries(updates)) {
      if (['title', 'description', 'url', 'category', 'media_type', 'sort_order', 'is_published'].includes(key)) {
        fields.push(`${key} = $${idx}`);
        values.push(val);
        idx++;
      }
    }

    if (fields.length === 0) throw new Error('No valid fields to update');
    values.push(id);

    const query = `
      UPDATE public.media
      SET ${fields.join(', ')}
      WHERE id = $${idx}
      RETURNING id, title, description, url, category, media_type, sort_order, is_published, created_at;
    `;
    const res = await pool.query(query, values);
    if (res.rowCount === 0) throw new Error('Record not found');
    const row = res.rows[0];
    return {
      id: row.id,
      title: row.title,
      description: row.description,
      url: row.url,
      category: row.category,
      media_type: row.media_type,
      sort_order: row.sort_order,
      is_published: row.is_published,
      created_at: row.created_at instanceof Date ? row.created_at.toISOString() : String(row.created_at),
    };
  }

  throw new Error('Database connection not configured');
}

/**
 * Deletes a media record by ID.
 */
export async function deleteMediaRecordFromDb(id: string): Promise<boolean> {
  const supabase = getSupabaseAdminClient();
  if (supabase) {
    const { error } = await supabase.from('media').delete().eq('id', id);
    if (error) throw new Error(error.message);
    return true;
  }

  const pool = getPgPool();
  if (pool) {
    const res = await pool.query('DELETE FROM public.media WHERE id = $1;', [id]);
    return (res.rowCount ?? 0) > 0;
  }

  throw new Error('Database connection not configured');
}

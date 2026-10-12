export type MediaType = 'image' | 'video' | 'link';

export interface MediaRecord {
  id: string;
  title: string;
  description: string;
  url: string;
  category: string;
  media_type: MediaType;
  sort_order: number;
  is_published: boolean;
  created_at: string;
}

/**
 * Public response contract for the scrapbook frontend:
 * Matches required format:
 * { "id": "...", "title": "...", "description": "...", "url": "...", "category": "...", "media_type": "image", "sort_order": 0, "created_at": "..." }
 */
export interface PublicMediaItem {
  id: string;
  title: string;
  description: string;
  url: string;
  category: string;
  media_type: MediaType;
  sort_order: number;
  created_at: string;
}

export interface MediaListResponse {
  media: PublicMediaItem[];
}

export interface MediaCreateResponse {
  media: MediaRecord;
  message?: string;
}

export interface ApiErrorResponse {
  error: string;
  details?: unknown;
}

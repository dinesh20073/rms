import { z } from 'zod';
import { MediaType } from './types';

export const MEDIA_TYPES: [MediaType, ...MediaType[]] = ['image', 'video', 'link'];

/**
 * Normalizes or extracts useful information from Google Drive URLs.
 * Handles:
 * - https://drive.google.com/file/d/<FILE_ID>/view?usp=sharing
 * - https://drive.google.com/open?id=<FILE_ID>
 * - https://drive.google.com/uc?id=<FILE_ID>
 */
export function parseGoogleDriveUrl(rawUrl: string): { isGoogleDrive: boolean; fileId: string | null; directViewUrl: string | null } {
  try {
    const parsed = new URL(rawUrl);
    if (!parsed.hostname.includes('drive.google.com')) {
      return { isGoogleDrive: false, fileId: null, directViewUrl: null };
    }

    let fileId: string | null = null;
    const pathParts = parsed.pathname.split('/');
    const dIndex = pathParts.indexOf('d');
    if (dIndex !== -1 && pathParts[dIndex + 1]) {
      fileId = pathParts[dIndex + 1];
    } else if (parsed.searchParams.has('id')) {
      fileId = parsed.searchParams.get('id');
    }

    return {
      isGoogleDrive: true,
      fileId,
      directViewUrl: fileId ? `https://drive.google.com/uc?export=view&id=${fileId}` : null,
    };
  } catch {
    return { isGoogleDrive: false, fileId: null, directViewUrl: null };
  }
}

export const createMediaSchema = z.object({
  title: z
    .string({ required_error: 'Title is required' })
    .trim()
    .min(1, 'Title cannot be empty')
    .max(255, 'Title must not exceed 255 characters'),
  description: z
    .string()
    .trim()
    .max(2000, 'Description must not exceed 2000 characters')
    .optional()
    .default(''),
  url: z
    .string({ required_error: 'URL is required' })
    .trim()
    .max(2048, 'URL must not exceed 2048 characters')
    .refine((val) => {
      try {
        const u = new URL(val);
        return u.protocol === 'https:';
      } catch {
        return false;
      }
    }, 'URL must be a valid HTTPS URL (e.g., https://... or Google Drive share link)'),
  category: z
    .string()
    .trim()
    .max(50, 'Category must not exceed 50 characters')
    .optional()
    .default('gathering'),
  media_type: z.enum(MEDIA_TYPES, {
    errorMap: () => ({ message: "media_type must be either 'image', 'video', or 'link'" }),
  }),
  sort_order: z.coerce
    .number()
    .int('sort_order must be an integer')
    .min(-100000, 'sort_order is too small')
    .max(100000, 'sort_order is too large')
    .optional()
    .default(0),
  is_published: z.boolean().optional().default(true),
});

export type CreateMediaInput = z.infer<typeof createMediaSchema>;

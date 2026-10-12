import { NextRequest, NextResponse } from 'next/server';
import crypto from 'crypto';
import {
  getPublishedMediaRecords,
  getAllMediaRecords,
  createMediaRecordInDb,
  updateMediaRecordInDb,
  deleteMediaRecordFromDb,
} from '@/lib/supabase';
import { getCorsHeaders, handleCorsPreflight } from '@/lib/cors';
import { createMediaSchema } from '@/lib/validators';
import { MediaListResponse, MediaCreateResponse, ApiErrorResponse } from '@/lib/types';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

/**
 * OPTIONS /api/media
 * Handles CORS preflight requests.
 */
export async function OPTIONS(request: NextRequest) {
  return handleCorsPreflight(request);
}

/**
 * Validates the Authorization header using constant-time string comparison.
 */
function verifyAdminApiKey(authHeader: string | null): boolean {
  const configuredKey = process.env.ADMIN_API_KEY?.trim();
  if (!configuredKey) {
    console.warn('[Media API - Security Warning] ADMIN_API_KEY is not configured in environment');
    return false;
  }

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return false;
  }

  const token = authHeader.substring(7).trim();
  if (!token) {
    return false;
  }

  try {
    const tokenBuffer = Buffer.from(token);
    const configuredBuffer = Buffer.from(configuredKey);

    if (tokenBuffer.length !== configuredBuffer.length) {
      return false;
    }

    return crypto.timingSafeEqual(tokenBuffer, configuredBuffer);
  } catch {
    return false;
  }
}

/**
 * GET /api/media
 * Retrieves media records. If `?admin=true` and valid Admin Bearer token is passed,
 * returns all records (including unpublished). Otherwise returns public published records.
 */
export async function GET(request: NextRequest) {
  const origin = request.headers.get('origin');
  const corsHeaders = getCorsHeaders(origin);
  const searchParams = request.nextUrl.searchParams;
  const isAdminRequest = searchParams.get('admin') === 'true';

  try {
    if (isAdminRequest) {
      const authHeader = request.headers.get('authorization');
      if (!verifyAdminApiKey(authHeader)) {
        return NextResponse.json<ApiErrorResponse>(
          { error: 'Unauthorized: Missing or invalid Admin Bearer token' },
          { status: 401, headers: corsHeaders }
        );
      }
      const allRecords = await getAllMediaRecords();
      return NextResponse.json({ media: allRecords }, { status: 200, headers: corsHeaders });
    }

    // Public request
    const data = await getPublishedMediaRecords();
    const responsePayload: MediaListResponse = {
      media: data || [],
    };

    return NextResponse.json(responsePayload, {
      status: 200,
      headers: {
        ...corsHeaders,
        'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=300',
      },
    });
  } catch (err: unknown) {
    const errorMessage = err instanceof Error ? err.message : 'Unknown error';
    console.error('[Media API - GET Error]', errorMessage);

    return NextResponse.json<ApiErrorResponse>(
      { error: 'Failed to retrieve media records from database' },
      { status: 500, headers: corsHeaders }
    );
  }
}

/**
 * POST /api/media
 * Adds a new media record (Admin only).
 */
export async function POST(request: NextRequest) {
  const origin = request.headers.get('origin');
  const corsHeaders = getCorsHeaders(origin);

  const authHeader = request.headers.get('authorization');
  if (!verifyAdminApiKey(authHeader)) {
    return NextResponse.json<ApiErrorResponse>(
      { error: 'Unauthorized: Missing or invalid Admin Bearer token' },
      { status: 401, headers: corsHeaders }
    );
  }

  const contentLength = request.headers.get('content-length');
  if (contentLength && parseInt(contentLength, 10) > 65536) {
    return NextResponse.json<ApiErrorResponse>(
      { error: 'Payload too large: Max payload size is 64KB' },
      { status: 413, headers: corsHeaders }
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json<ApiErrorResponse>(
      { error: 'Invalid JSON request body' },
      { status: 400, headers: corsHeaders }
    );
  }

  const validationResult = createMediaSchema.safeParse(body);
  if (!validationResult.success) {
    const errorDetails = validationResult.error.errors.map((issue) => ({
      field: issue.path.join('.'),
      message: issue.message,
    }));

    return NextResponse.json<ApiErrorResponse>(
      {
        error: 'Validation failed: Check provided fields',
        details: errorDetails,
      },
      { status: 400, headers: corsHeaders }
    );
  }

  const { title, description, url, category, media_type, sort_order, is_published } = validationResult.data;

  try {
    const data = await createMediaRecordInDb({
      title,
      description: description || '',
      url,
      category: category || 'gathering',
      media_type,
      sort_order: sort_order ?? 0,
      is_published: is_published ?? true,
    });

    const responsePayload: MediaCreateResponse = {
      media: data,
      message: 'Media record created successfully',
    };

    return NextResponse.json(responsePayload, {
      status: 201,
      headers: corsHeaders,
    });
  } catch (err: unknown) {
    const errorMessage = err instanceof Error ? err.message : 'Unknown error';
    console.error('[Media API - POST Error]', errorMessage);

    return NextResponse.json<ApiErrorResponse>(
      { error: 'Failed to save media record to database' },
      { status: 500, headers: corsHeaders }
    );
  }
}

/**
 * PATCH /api/media
 * Updates an existing media record (Admin only).
 */
export async function PATCH(request: NextRequest) {
  const origin = request.headers.get('origin');
  const corsHeaders = getCorsHeaders(origin);

  const authHeader = request.headers.get('authorization');
  if (!verifyAdminApiKey(authHeader)) {
    return NextResponse.json<ApiErrorResponse>(
      { error: 'Unauthorized: Missing or invalid Admin Bearer token' },
      { status: 401, headers: corsHeaders }
    );
  }

  let body: any;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json<ApiErrorResponse>({ error: 'Invalid JSON request body' }, { status: 400, headers: corsHeaders });
  }

  const { id, ...updates } = body;
  if (!id) {
    return NextResponse.json<ApiErrorResponse>({ error: 'Missing media record id' }, { status: 400, headers: corsHeaders });
  }

  try {
    const updated = await updateMediaRecordInDb(id, updates);
    return NextResponse.json({ media: updated, message: 'Record updated successfully' }, { status: 200, headers: corsHeaders });
  } catch (err: unknown) {
    const errorMessage = err instanceof Error ? err.message : 'Unknown error';
    return NextResponse.json<ApiErrorResponse>({ error: errorMessage }, { status: 500, headers: corsHeaders });
  }
}

/**
 * DELETE /api/media?id=UUID
 * Deletes a media record (Admin only).
 */
export async function DELETE(request: NextRequest) {
  const origin = request.headers.get('origin');
  const corsHeaders = getCorsHeaders(origin);

  const authHeader = request.headers.get('authorization');
  if (!verifyAdminApiKey(authHeader)) {
    return NextResponse.json<ApiErrorResponse>(
      { error: 'Unauthorized: Missing or invalid Admin Bearer token' },
      { status: 401, headers: corsHeaders }
    );
  }

  const searchParams = request.nextUrl.searchParams;
  const id = searchParams.get('id');

  if (!id) {
    return NextResponse.json<ApiErrorResponse>({ error: 'Missing id query parameter' }, { status: 400, headers: corsHeaders });
  }

  try {
    const deleted = await deleteMediaRecordFromDb(id);
    if (!deleted) {
      return NextResponse.json<ApiErrorResponse>({ error: 'Media record not found' }, { status: 404, headers: corsHeaders });
    }
    return NextResponse.json({ success: true, message: 'Record deleted successfully' }, { status: 200, headers: corsHeaders });
  } catch (err: unknown) {
    const errorMessage = err instanceof Error ? err.message : 'Unknown error';
    return NextResponse.json<ApiErrorResponse>({ error: errorMessage }, { status: 500, headers: corsHeaders });
  }
}

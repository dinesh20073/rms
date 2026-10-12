import { NextResponse } from 'next/server';

/**
 * Parses and returns list of allowed origins from FRONTEND_ORIGIN env var.
 * Supports single URL or comma-separated URLs (e.g. "https://nizhalcommunity.in,http://localhost:5173").
 */
export function getAllowedOrigins(): string[] {
  const configured = process.env.FRONTEND_ORIGIN;
  if (!configured) {
    // Default safe fallback in development
    return ['https://nizhalcommunity.in', 'http://localhost:5173', 'http://localhost:3000'];
  }
  return configured
    .split(',')
    .map((o) => o.trim().replace(/\/$/, ''))
    .filter(Boolean);
}

/**
 * Determines whether a requested origin is allowed and returns it.
 */
export function resolveAllowedOrigin(requestOrigin: string | null): string | null {
  if (!requestOrigin) {
    const allowed = getAllowedOrigins();
    return allowed[0] || null;
  }

  const cleanRequestOrigin = requestOrigin.trim().replace(/\/$/, '');
  const allowed = getAllowedOrigins();

  const match = allowed.find((o) => o.toLowerCase() === cleanRequestOrigin.toLowerCase());
  if (match) {
    return match;
  }

  // If FRONTEND_ORIGIN is explicitly set to wildcard '*' (only if user intentionally configures it)
  if (allowed.includes('*')) {
    return '*';
  }

  return null;
}

/**
 * Builds standard CORS headers for API responses.
 */
export function getCorsHeaders(requestOrigin: string | null): Record<string, string> {
  const resolved = resolveAllowedOrigin(requestOrigin);
  const headers: Record<string, string> = {
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Max-Age': '86400',
    'Vary': 'Origin',
  };

  if (resolved) {
    headers['Access-Control-Allow-Origin'] = resolved;
  }

  return headers;
}

/**
 * Handles CORS OPTIONS preflight request.
 */
export function handleCorsPreflight(request: Request): NextResponse {
  const origin = request.headers.get('origin');
  const headers = getCorsHeaders(origin);

  return new NextResponse(null, {
    status: 204,
    headers,
  });
}

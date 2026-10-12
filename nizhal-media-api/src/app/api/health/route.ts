import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function GET() {
  return NextResponse.json({
    status: 'healthy',
    service: 'nizhal-media-api',
    timestamp: new Date().toISOString(),
  });
}

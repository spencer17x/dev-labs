import { NextResponse } from 'next/server';

import {
  parseRuntimeIngestInput,
} from '@/lib/runtime/runtime-ingest';
import { ingestSignalEvents } from '@/lib/runtime/refresh-feed';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(request: Request): Promise<NextResponse> {
  const body = (await request.json().catch(() => null)) as {
    limit?: number;
    payload?: unknown;
    payloadText?: string;
    subscription?: string;
  } | null;

  if (!body) {
    return NextResponse.json({ message: 'invalid request body' }, { status: 400 });
  }

  let payload = body.payload;
  if (typeof body.payloadText === 'string' && body.payloadText.trim()) {
    try {
      payload = JSON.parse(body.payloadText);
    } catch {
      return NextResponse.json({ message: 'invalid payloadText' }, { status: 400 });
    }
  }

  if (payload === undefined) {
    return NextResponse.json({ message: 'payload is required' }, { status: 400 });
  }

  const { events, subscription } = parseRuntimeIngestInput({
    limit: body.limit,
    payload,
    subscription: body.subscription,
  });
  const result = await ingestSignalEvents(events, {
    dexTokenDetailsMaxWaitMs: 750,
  });

  return NextResponse.json({
    subscription,
    ...result,
  });
}

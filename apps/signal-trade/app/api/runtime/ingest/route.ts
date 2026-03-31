import { NextResponse } from 'next/server';

import {
  normalizeDexSubscriptions,
  parseDexSubscriptionPayload,
} from '@/lib/runtime/dexscreener';
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

  const subscription = normalizeDexSubscriptions(
    typeof body.subscription === 'string' ? [body.subscription] : undefined,
  )[0];
  const limit =
    typeof body.limit === 'number' && body.limit > 0 ? Math.trunc(body.limit) : 10;
  const events = parseDexSubscriptionPayload(subscription, payload, limit);
  const result = await ingestSignalEvents(events);

  return NextResponse.json({
    subscription,
    ...result,
  });
}

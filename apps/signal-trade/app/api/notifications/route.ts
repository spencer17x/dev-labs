import { NextResponse } from 'next/server';

import { getNotificationFeed } from '@/lib/signal-trade-data';

export async function GET(): Promise<NextResponse> {
  const notifications = await getNotificationFeed();
  return NextResponse.json({ notifications });
}

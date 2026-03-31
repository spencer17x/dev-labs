import { NextResponse } from 'next/server';

import { refreshNotificationFeed } from '@/lib/runtime/refresh-feed';

export async function POST(request: Request): Promise<NextResponse> {
  try {
    const body = (await request.json().catch(() => ({}))) as {
      limit?: number;
      subscriptions?: string[];
    };

    const result = await refreshNotificationFeed({
      limit: body.limit,
      subscriptions: body.subscriptions,
    });

    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      {
        error: 'refresh_failed',
        message: error instanceof Error ? error.message : 'Unknown refresh error',
      },
      { status: 500 },
    );
  }
}

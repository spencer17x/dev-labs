import {
  fetchDexSubscriptionOnce,
  normalizeDexSubscriptions,
} from '@/lib/runtime/dexscreener';
import { enrichSignalEvent } from '@/lib/runtime/enrichment';
import {
  buildNotificationRecords,
  type StoredSignal,
} from '@/lib/runtime/notification-store';
import type { NotificationRecord, RuntimeRefreshResult, SignalEvent } from '@/lib/types';

type RefreshOptions = {
  limit?: number;
  subscriptions?: string[];
};

export async function refreshNotificationFeed(
  options: RefreshOptions = {},
): Promise<RuntimeRefreshResult> {
  const subscriptions = normalizeDexSubscriptions(options.subscriptions);
  const limit = typeof options.limit === 'number' && options.limit > 0 ? options.limit : 10;
  const events: SignalEvent[] = [];

  for (const subscription of subscriptions) {
    events.push(...(await fetchDexSubscriptionOnce(subscription, limit)));
  }

  const result = await ingestSignalEvents(events);

  return {
    generatedAt: new Date().toISOString(),
    stored: result.stored,
    notifications: result.notifications,
    processed: result.processed,
    subscriptions,
  };
}

export async function ingestSignalEvents(events: SignalEvent[]): Promise<{
  notifications: NotificationRecord[];
  processed: number;
  stored: number;
}> {
  if (events.length === 0) {
    return {
      notifications: [],
      processed: 0,
      stored: 0,
    };
  }

  const signals: StoredSignal[] = [];
  for (const event of events) {
    const context = await enrichSignalEvent(event);
    signals.push({ event, context });
  }

  const notifications = buildNotificationRecords(signals);

  return {
    notifications,
    processed: events.length,
    stored: notifications.length,
  };
}

import {
  buildDexTokenDetailKey,
  fetchDexTokenDetailsByChain,
  type DexTokenPairDetails,
} from '@/lib/dexscreener-token-details';
import { mergeSignalContextWithDexTokenDetail } from '@/lib/dex-token-context';
import {
  fetchDexSubscriptionOnce,
  normalizeDexSubscriptions,
} from '@/lib/runtime/dexscreener';
import { enrichSignalEvent } from '@/lib/runtime/enrichment';
import {
  buildNotificationRecords,
  type StoredSignal,
} from '@/lib/runtime/notification-store';
import { hydrateStoredSignalsWithTokenDetails } from '@/lib/runtime/signal-token-hydration';
import type { NotificationRecord, RuntimeRefreshResult, SignalEvent } from '@/lib/types';

type RefreshOptions = {
  limit?: number;
  subscriptions?: string[];
};

type IngestSignalEventsOptions = {
  dexTokenDetailsMaxWaitMs?: number;
};

type HydrateSignalsOptions = {
  fetchDetailsByChain?: typeof fetchDexTokenDetailsByChain;
  maxWaitMs?: number;
};

const LIVE_INGEST_DEX_TOKEN_DETAILS_MAX_WAIT_MS = 750;

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
}>;
export async function ingestSignalEvents(
  events: SignalEvent[],
  options: IngestSignalEventsOptions,
): Promise<{
  notifications: NotificationRecord[];
  processed: number;
  stored: number;
}>;
export async function ingestSignalEvents(
  events: SignalEvent[],
  options: IngestSignalEventsOptions = {},
): Promise<{
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

  const notifications = buildNotificationRecords(
    await hydrateSignalsWithDexTokenDetails(signals, {
      maxWaitMs: options.dexTokenDetailsMaxWaitMs,
    }),
  );

  return {
    notifications,
    processed: events.length,
    stored: notifications.length,
  };
}

export async function hydrateSignalsWithDexTokenDetails(
  signals: StoredSignal[],
  options: HydrateSignalsOptions = {},
): Promise<StoredSignal[]> {
  const fetchDetailsByChain = options.fetchDetailsByChain ?? fetchDexTokenDetailsByChain;
  const maxWaitMs =
    typeof options.maxWaitMs === 'number' && options.maxWaitMs >= 0
      ? options.maxWaitMs
      : LIVE_INGEST_DEX_TOKEN_DETAILS_MAX_WAIT_MS;
  return hydrateStoredSignalsWithTokenDetails<StoredSignal, DexTokenPairDetails>(signals, {
    buildTokenKey: buildDexTokenDetailKey,
    fetchDetailsByChain,
    maxWaitMs,
    mergeSignalWithDetail: (signal, detail) => ({
      ...signal,
      context: mergeSignalContextWithDexTokenDetail(signal.context, detail),
    }),
  });
}

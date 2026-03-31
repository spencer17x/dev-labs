import type {
  NotificationRecord,
  SignalContext,
  SignalEvent,
} from '@/lib/types';

export type StoredSignal = {
  context: SignalContext;
  event: SignalEvent;
};

export function buildNotificationRecords(
  signals: StoredSignal[],
): NotificationRecord[] {
  const records: NotificationRecord[] = [];
  const seenIds = new Set<string>();

  for (const signal of signals) {
    const record = buildRecord(signal);
    if (seenIds.has(record.id)) {
      continue;
    }

    seenIds.add(record.id);
    records.push(record);
  }

  return records;
}

export function getNotificationStoreStats(): {
  count: number;
  isEmpty: boolean;
  mode: 'none';
  resetsOnRestart: boolean;
} {
  return {
    count: 0,
    isEmpty: true,
    mode: 'none',
    resetsOnRestart: false,
  };
}

function buildRecord(signal: StoredSignal): NotificationRecord {
  return {
    id: signal.event.id,
    notifiedAt: new Date().toISOString(),
    channels: [],
    message: buildNotificationMessage(signal.event, signal.context),
    event: signal.event,
    context: signal.context,
    summary: {
      paid:
        Boolean(signal.context.dexscreener?.paid) ||
        signal.event.subtype === 'token_profiles_latest',
      imageUrl:
        asString(signal.context.dexscreener?.imageUrl) ??
        asString(signal.context.dexscreener?.icon),
      marketCap:
        asNumber(signal.context.xxyy?.market_cap) ??
        asNumber(signal.context.dexscreener?.marketCap),
      holderCount: asNumber(signal.context.xxyy?.holder_count),
      liquidityUsd:
        asNumber(signal.context.xxyy?.liquidity) ??
        asNumber(signal.context.dexscreener?.liquidityUsd),
      priceUsd:
        asNumber(signal.context.xxyy?.price_usd) ??
        asNumber(signal.context.dexscreener?.priceUsd),
      communityCount: asNumber(signal.context.twitter?.community_count),
      followersCount: asNumber(signal.context.twitter?.followers_count),
      twitterUsername:
        typeof signal.context.twitter?.username === 'string'
          ? signal.context.twitter.username
          : null,
      dexscreenerUrl:
        typeof signal.context.dexscreener?.url === 'string'
          ? signal.context.dexscreener.url
          : null,
      telegramUrl:
        typeof signal.context.xxyy?.project_telegram_url === 'string'
          ? signal.context.xxyy.project_telegram_url
          : null,
    },
  };
}

function buildNotificationMessage(
  event: SignalEvent,
  context: SignalContext,
): string {
  const tokenRef =
    asString(context.token?.symbol) ||
    event.token.symbol ||
    asString(context.token?.address) ||
    event.token.address ||
    'unknown-token';

  return [
    `source=${event.source}.${event.subtype}`,
    `token=${tokenRef}`,
    `market_cap=${asNumber(context.xxyy?.market_cap) ?? asNumber(context.dexscreener?.marketCap) ?? 'n/a'}`,
    `holders=${asNumber(context.xxyy?.holder_count) ?? 'n/a'}`,
    `twitter_community=${asNumber(context.twitter?.community_count) ?? 'n/a'}`,
  ].join(' ');
}

function asNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

import type {
  NotificationRecord,
  SignalContext,
  SignalEvent,
} from '../types';

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
      marketCap: asNumber(signal.context.dexscreener?.marketCap),
      holderCount: readRawNumber(
        signal.event.raw,
        'holderCount',
        'holdersCount',
        'holder_count',
        'holders',
      ),
      liquidityUsd: asNumber(signal.context.dexscreener?.liquidityUsd),
      priceUsd: asNumber(signal.context.dexscreener?.priceUsd),
      communityCount: readRawNumber(
        signal.event.raw,
        'communityCount',
        'community_count',
      ),
      dexscreenerUrl:
        typeof signal.context.dexscreener?.url === 'string'
          ? signal.context.dexscreener.url
          : null,
      telegramUrl: findLinkUrl(signal.context.dexscreener?.links, ['telegram']),
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
    asString(context.dexscreener?.header),
    asString(context.dexscreener?.description),
    asString(event.text),
    `source=${event.source}.${event.subtype}`,
    `token=${tokenRef}`,
    formatMetric('market_cap', asNumber(context.dexscreener?.marketCap)),
    formatMetric('liquidity_usd', asNumber(context.dexscreener?.liquidityUsd)),
    formatMetric('price_usd', asNumber(context.dexscreener?.priceUsd)),
    formatMetric('active_boosts', asNumber(event.metrics?.activeBoosts)),
    formatMetric('amount', asNumber(event.metrics?.amount)),
    formatMetric('total_amount', asNumber(event.metrics?.totalAmount)),
  ]
    .filter(Boolean)
    .join(' | ');
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

function readRawNumber(
  value: unknown,
  ...keys: string[]
): number | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }

  for (const key of keys) {
    const parsed = asNumber((value as Record<string, unknown>)[key]);
    if (parsed !== null) {
      return parsed;
    }
  }

  return null;
}

function findLinkUrl(
  links: unknown,
  expectedTypes: string[],
): string | null {
  if (!Array.isArray(links)) {
    return null;
  }

  const normalizedTypes = new Set(expectedTypes.map(item => item.toLowerCase()));
  for (const link of links) {
    if (!link || typeof link !== 'object' || Array.isArray(link)) {
      continue;
    }
    const type = asString((link as Record<string, unknown>).type)?.toLowerCase();
    if (!type || !normalizedTypes.has(type)) {
      continue;
    }
    const url = asString((link as Record<string, unknown>).url);
    if (url) {
      return url;
    }
  }

  return null;
}

function formatMetric(label: string, value: number | null): string | null {
  if (value === null) {
    return null;
  }
  return `${label}=${value}`;
}

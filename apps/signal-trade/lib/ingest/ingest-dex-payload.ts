import type {
  DexScreenerLatestItemBySubscription,
  DexScreenerLatestPayload,
  DexScreenerLatestSubscription,
  DexScreenerLatestWsResponse,
  DexScreenerLinkRaw,
} from '../dexscreener-api-types';
import {
  buildDexTokenDetailKey,
  fetchDexTokenDetailsByChain,
  type DexTokenPairDetails,
} from '../dexscreener-token-details';
import { mergeSignalContextWithDexTokenDetail } from '../dex-token-context';
import type { NotificationRecord, SignalEvent } from '../types';
import { enrichSignalEvent } from './enrich-signal-event';
import {
  buildNotificationRecords,
  type StoredSignal,
} from './build-notification-records';
import { hydrateStoredSignalsWithTokenDetails } from './hydrate-signals-with-token-details';

export const ALL_DEX_SUBSCRIPTIONS = [
  'token_profiles_latest',
  'community_takeovers_latest',
  'ads_latest',
  'token_boosts_latest',
  'token_boosts_top',
] as const;

export type DexScreenerSubscription = (typeof ALL_DEX_SUBSCRIPTIONS)[number];

export type FetchTokenDetailsByChain = (
  chainId: string,
  tokenAddresses: string[],
) => Promise<Record<string, DexTokenPairDetails | null>>;

export type IngestDexPayloadOptions = {
  fetchDetailsByChain?: FetchTokenDetailsByChain;
  limit?: number;
  maxWaitMs?: number;
  payload: unknown;
  subscription?: string;
};

export type IngestDexPayloadTextOptions = Omit<IngestDexPayloadOptions, 'payload'> & {
  payloadText: string;
};

export async function ingestDexPayload(
  options: IngestDexPayloadOptions,
): Promise<{
  notifications: NotificationRecord[];
  processed: number;
  stored: number;
  subscription: DexScreenerSubscription;
}> {
  const subscription = normalizeDexSubscriptions(
    typeof options.subscription === 'string' ? [options.subscription] : undefined,
  )[0];
  const limit =
    typeof options.limit === 'number' && options.limit > 0
      ? Math.trunc(options.limit)
      : undefined;
  const events = parseDexSubscriptionPayload(subscription, options.payload, limit);
  const notifications = await ingestSignalEvents(events, {
    fetchDetailsByChain: options.fetchDetailsByChain,
    maxWaitMs: options.maxWaitMs,
  });

  return {
    notifications,
    processed: events.length,
    stored: notifications.length,
    subscription,
  };
}

export async function ingestDexPayloadText(
  options: IngestDexPayloadTextOptions,
): Promise<{
  notifications: NotificationRecord[];
  processed: number;
  stored: number;
  subscription: DexScreenerSubscription;
}> {
  let payload: unknown;
  try {
    payload = JSON.parse(options.payloadText);
  } catch {
    throw new Error('invalid payloadText');
  }

  return ingestDexPayload({
    fetchDetailsByChain: options.fetchDetailsByChain,
    limit: options.limit,
    maxWaitMs: options.maxWaitMs,
    payload,
    subscription: options.subscription,
  });
}

export function normalizeDexSubscriptions(
  value: string[] | undefined,
): DexScreenerSubscription[] {
  if (!Array.isArray(value) || value.length === 0) {
    return ['token_profiles_latest'];
  }

  const allowed = new Set<string>(ALL_DEX_SUBSCRIPTIONS);
  const normalized = value.filter(
    (item): item is DexScreenerSubscription => allowed.has(item),
  );

  return normalized.length > 0 ? normalized : ['token_profiles_latest'];
}

export function parseDexSubscriptionPayload(
  subscription: DexScreenerSubscription,
  payload: DexScreenerLatestPayload<DexScreenerSubscription> | unknown,
  limit?: number,
): SignalEvent[] {
  const items = extractItems(subscription, payload).slice(
    0,
    limit && limit > 0 ? limit : undefined,
  );
  return items.map(item => buildEvent(subscription, item));
}

async function ingestSignalEvents(
  events: SignalEvent[],
  options: {
    fetchDetailsByChain?: FetchTokenDetailsByChain;
    maxWaitMs?: number;
  } = {},
): Promise<NotificationRecord[]> {
  if (events.length === 0) {
    return [];
  }

  const signals: StoredSignal[] = [];
  for (const event of events) {
    const context = await enrichSignalEvent(event);
    signals.push({ event, context });
  }

  return buildNotificationRecords(
    await hydrateStoredSignalsWithTokenDetails(signals, {
      buildTokenKey: buildDexTokenDetailKey,
      fetchDetailsByChain: options.fetchDetailsByChain ?? fetchDexTokenDetailsByChain,
      maxWaitMs:
        typeof options.maxWaitMs === 'number' && options.maxWaitMs >= 0
          ? options.maxWaitMs
          : 750,
      mergeSignalWithDetail: (signal, detail) => ({
        ...signal,
        context: mergeSignalContextWithDexTokenDetail(signal.context, detail),
      }),
    }),
  );
}

function buildEvent(
  subscription: DexScreenerSubscription,
  item: DexScreenerLatestItemBySubscription[DexScreenerSubscription],
): SignalEvent {
  const looseItem = item as Record<string, unknown>;
  const chainId = coalesce(
    item.chainId,
    asString(looseItem.chain),
    asString(looseItem.network),
  );
  const tokenAddress = coalesce(
    item.tokenAddress,
    asString(looseItem.address),
    deepGet(looseItem, 'token', 'address'),
  );

  return {
    id: buildEventId(subscription, chainId, tokenAddress, item),
    source: 'dexscreener',
    subtype: subscription,
    timestamp: normalizeTimestamp(
      coalesceNumber(
        asNumber(looseItem.paymentTimestamp),
        asNumber(looseItem.timestamp),
        asNumber(looseItem.createdAt),
        asNumber(looseItem.updatedAt),
      ),
    ),
    chain: chainId,
    token: {
      symbol: coalesce(
        asString(looseItem.symbol),
        deepGet(looseItem, 'token', 'symbol'),
      ),
      name: coalesce(
        asString(looseItem.tokenName),
        asString(looseItem.name),
        deepGet(looseItem, 'token', 'name'),
      ),
      address: tokenAddress,
    },
    author: buildAuthor(item),
    text: coalesce(
      typeof item.description === 'string' ? item.description : null,
      asString(looseItem.title),
    ),
    metrics: extractMetrics(item),
    raw: item,
    metadata: {
      subscription,
      dexscreener: {
        url: item.url,
        icon: 'icon' in item ? normalizeOptionalString(item.icon) : null,
        header: 'header' in item ? normalizeOptionalString(item.header) : null,
        description:
          'description' in item ? normalizeOptionalString(item.description) : null,
        links: extractLinks(asLinkArray(looseItem.links)),
      },
    },
  };
}

function buildAuthor(
  item: DexScreenerLatestItemBySubscription[DexScreenerSubscription],
): SignalEvent['author'] {
  const looseItem = item as Record<string, unknown>;
  const authorName = coalesce(
    asString(looseItem.author),
    asString(looseItem.projectOwner),
    asString(looseItem.project),
  );
  if (!authorName) {
    return null;
  }
  return {
    display_name: authorName,
  };
}

function extractMetrics(
  item: DexScreenerLatestItemBySubscription[DexScreenerSubscription],
): Record<string, number> {
  const looseItem = item as Record<string, unknown>;
  const metrics: Record<string, number> = {};
  const candidates: Record<string, unknown> = {
    amount: 'amount' in item ? item.amount : looseItem.amount,
    totalAmount: 'totalAmount' in item ? item.totalAmount : looseItem.totalAmount,
    activeBoosts: deepGet(looseItem, 'boosts', 'active'),
  };

  for (const [key, value] of Object.entries(candidates)) {
    const parsed = asNumber(value);
    if (parsed !== null) {
      metrics[key] = parsed;
    }
  }

  return metrics;
}

function extractItems<TSubscription extends DexScreenerSubscription>(
  _subscription: TSubscription,
  payload: DexScreenerLatestPayload<TSubscription> | unknown,
): Array<DexScreenerLatestItemBySubscription[TSubscription]> {
  if (Array.isArray(payload)) {
    return payload.filter(isObject) as Array<
      DexScreenerLatestItemBySubscription[TSubscription]
    >;
  }

  if (isObject(payload)) {
    const data = (payload as DexScreenerLatestWsResponse<TSubscription>).data;
    if (Array.isArray(data)) {
      return data.filter(isObject) as Array<
        DexScreenerLatestItemBySubscription[TSubscription]
      >;
    }

    return [payload as DexScreenerLatestItemBySubscription[TSubscription]];
  }

  return [];
}

function extractLinks(
  value: DexScreenerLinkRaw[] | null | undefined,
): Array<Record<string, string>> {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .filter(isObject)
    .map(item => ({
      type: String(item.type ?? '').trim(),
      label: String(item.label ?? '').trim(),
      url: String(item.url ?? '').trim(),
    }))
    .filter(item => item.url);
}

function asLinkArray(value: unknown): DexScreenerLinkRaw[] | null | undefined {
  if (value === null) {
    return null;
  }

  return Array.isArray(value) ? (value as DexScreenerLinkRaw[]) : undefined;
}

function buildEventId(
  subscription: DexScreenerSubscription,
  chainId: string | null,
  tokenAddress: string | null,
  item: DexScreenerLatestItemBySubscription[DexScreenerSubscription],
): string {
  const looseItem = item as Record<string, unknown>;
  const stableBits = [
    subscription,
    chainId ?? '',
    tokenAddress ?? '',
    String(looseItem.amount ?? ''),
    String(looseItem.totalAmount ?? ''),
    String(looseItem.paymentTimestamp ?? ''),
  ].join(':');

  if (stableBits.replace(/:/g, '')) {
    return stableBits;
  }

  return `${subscription}:${hashString(JSON.stringify(item))}`;
}

function hashString(value: string): string {
  let hash = 2166136261;

  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }

  return (hash >>> 0).toString(16).padStart(8, '0');
}

function normalizeTimestamp(value: number | null): number {
  if (value === null) {
    return Math.floor(Date.now() / 1000);
  }
  return value < 10_000_000_000 ? value : Math.floor(value / 1000);
}

function coalesce(...values: unknown[]): string | null {
  for (const value of values) {
    const parsed = asString(value);
    if (parsed) {
      return parsed;
    }
  }

  return null;
}

function coalesceNumber(...values: unknown[]): number | null {
  for (const value of values) {
    const parsed = asNumber(value);
    if (parsed !== null) {
      return parsed;
    }
  }

  return null;
}

function deepGet(
  payload: Record<string, unknown>,
  ...keys: string[]
): unknown {
  let current: unknown = payload;
  for (const key of keys) {
    if (!isObject(current)) {
      return null;
    }
    current = current[key];
  }
  return asString(current);
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

function normalizeOptionalString(value: unknown): string | null {
  return asString(value);
}

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

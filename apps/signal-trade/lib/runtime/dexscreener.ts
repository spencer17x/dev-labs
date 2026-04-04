import crypto from 'node:crypto';

import {
  DEXSCREENER_LATEST_SUBSCRIPTIONS,
  type DexScreenerLatestItemBySubscription,
  type DexScreenerLatestPayload,
  type DexScreenerLatestSubscription,
  type DexScreenerLatestWsResponse,
  type DexScreenerLinkRaw,
} from '../dexscreener-api-types';
import type { SignalEvent } from '../types';
import { signalTradeConfig } from './config';
import { withProxyEnvDisabled } from './proxy-env';

const DEXSCREENER_API_BASE = 'https://api.dexscreener.com';
const DEXSCREENER_WS_BASE = 'wss://api.dexscreener.com';
const MIN_STALE_TIMEOUT_MS = 15_000;

export const ALL_DEX_SUBSCRIPTIONS = DEXSCREENER_LATEST_SUBSCRIPTIONS;
export type DexScreenerSubscription = DexScreenerLatestSubscription;

const SUBSCRIPTION_ENDPOINTS: Record<DexScreenerSubscription, string> = {
  token_profiles_latest: '/token-profiles/latest/v1',
  community_takeovers_latest: '/community-takeovers/latest/v1',
  ads_latest: '/ads/latest/v1',
  token_boosts_latest: '/token-boosts/latest/v1',
  token_boosts_top: '/token-boosts/top/v1',
};

type DexStreamStatus =
  | 'connecting'
  | 'open'
  | 'error'
  | 'closed'
  | 'stale'
  | 'reconnecting';

export type DexStreamStatusEvent = {
  detail?: string;
  subscription: DexScreenerSubscription;
  type: DexStreamStatus;
};

type WatchDexSubscriptionsOptions = {
  limit?: number;
  onEvents: (
    events: SignalEvent[],
    subscription: DexScreenerSubscription,
  ) => Promise<void> | void;
  onStatus?: (event: DexStreamStatusEvent) => void;
  signal?: AbortSignal;
  staleAfterMs?: number;
  subscriptions: DexScreenerSubscription[];
};

export async function fetchDexSubscriptionOnce(
  subscription: DexScreenerSubscription,
  limit?: number,
): Promise<SignalEvent[]> {
  const url = new URL(
    SUBSCRIPTION_ENDPOINTS[subscription],
    DEXSCREENER_API_BASE,
  );

  const response = await withProxyEnvDisabled(async () =>
    fetch(url, {
      headers: {
        Accept: 'application/json',
      },
      next: { revalidate: 0 },
      signal: AbortSignal.timeout(signalTradeConfig.dexscreener.requestTimeoutSec * 1000),
    }),
  );
  if (!response.ok) {
    throw new Error(`dexscreener request failed: ${response.status}`);
  }

  const payload = (await response.json()) as unknown;
  return parseDexSubscriptionPayload(subscription, payload, limit);
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

export async function watchDexSubscriptions(
  options: WatchDexSubscriptionsOptions,
): Promise<void> {
  const tasks = options.subscriptions.map(subscription =>
    consumeDexSubscription(subscription, options),
  );
  await Promise.all(tasks);
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

async function consumeDexSubscription(
  subscription: DexScreenerSubscription,
  options: WatchDexSubscriptionsOptions,
): Promise<void> {
  while (!options.signal?.aborted) {
    try {
      await openDexSubscriptionSocket(subscription, options);
    } catch (error) {
      emitStatus(options.onStatus, {
        subscription,
        type: 'error',
        detail: error instanceof Error ? error.message : 'Unknown WebSocket error',
      });
    }

    if (options.signal?.aborted) {
      break;
    }

    emitStatus(options.onStatus, {
      subscription,
      type: 'reconnecting',
      detail: `retrying in ${signalTradeConfig.dexscreener.reconnectDelaySec}s`,
    });

    await sleep(
      signalTradeConfig.dexscreener.reconnectDelaySec * 1000,
      options.signal,
    );
  }
}

async function openDexSubscriptionSocket(
  subscription: DexScreenerSubscription,
  options: WatchDexSubscriptionsOptions,
): Promise<void> {
  const endpoint = buildSubscriptionWsUrl(subscription, options.limit);
  const staleAfterMs = Math.max(
    options.staleAfterMs ?? signalTradeConfig.dexscreener.wsHeartbeatSec * 2000,
    MIN_STALE_TIMEOUT_MS,
  );

  await new Promise<void>((resolve, reject) => {
    const socket = new WebSocket(endpoint);
    socket.binaryType = 'arraybuffer';

    let connectTimeout: ReturnType<typeof setTimeout> | null = setTimeout(() => {
      safeClose(socket, 1013, 'connect_timeout');
      reject(new Error(`connection timeout for ${subscription}`));
    }, signalTradeConfig.dexscreener.requestTimeoutSec * 1000);

    let staleTimeout: ReturnType<typeof setTimeout> | null = null;
    let settled = false;
    let processing = Promise.resolve();

    const cleanup = (): void => {
      if (connectTimeout) {
        clearTimeout(connectTimeout);
        connectTimeout = null;
      }
      if (staleTimeout) {
        clearTimeout(staleTimeout);
        staleTimeout = null;
      }
      options.signal?.removeEventListener('abort', handleAbort);
    };

    const finalizeResolve = (): void => {
      if (settled) {
        return;
      }
      settled = true;
      cleanup();
      resolve();
    };

    const finalizeReject = (error: Error): void => {
      if (settled) {
        return;
      }
      settled = true;
      cleanup();
      reject(error);
    };

    const resetStaleTimeout = (): void => {
      if (staleTimeout) {
        clearTimeout(staleTimeout);
      }
      staleTimeout = setTimeout(() => {
        emitStatus(options.onStatus, {
          subscription,
          type: 'stale',
          detail: `no messages for ${Math.round(staleAfterMs / 1000)}s`,
        });
        safeClose(socket, 1013, 'stale');
      }, staleAfterMs);
    };

    const handleAbort = (): void => {
      safeClose(socket, 1000, 'aborted');
      finalizeResolve();
    };

    options.signal?.addEventListener('abort', handleAbort, { once: true });

    emitStatus(options.onStatus, {
      subscription,
      type: 'connecting',
      detail: endpoint,
    });

    socket.addEventListener('open', () => {
      if (connectTimeout) {
        clearTimeout(connectTimeout);
        connectTimeout = null;
      }
      emitStatus(options.onStatus, { subscription, type: 'open' });
      resetStaleTimeout();
    });

    socket.addEventListener('message', event => {
      resetStaleTimeout();

      processing = processing
        .then(async () => {
          const payloadText = await readMessageText(event.data);
          if (!payloadText) {
            return;
          }

          let decoded: unknown;
          try {
            decoded = JSON.parse(payloadText);
          } catch {
            return;
          }

          const events = parseDexSubscriptionPayload(
            subscription,
            decoded,
            options.limit,
          );
          if (events.length === 0) {
            return;
          }

          await options.onEvents(events, subscription);
        })
        .catch(error => {
          emitStatus(options.onStatus, {
            subscription,
            type: 'error',
            detail:
              error instanceof Error
                ? error.message
                : 'Unknown message processing error',
          });
        });
    });

    socket.addEventListener('error', () => {
      emitStatus(options.onStatus, {
        subscription,
        type: 'error',
        detail: 'WebSocket transport error',
      });
    });

    socket.addEventListener('close', event => {
      void processing.finally(() => {
        emitStatus(options.onStatus, {
          subscription,
          type: 'closed',
          detail: `code=${event.code}${event.reason ? ` reason=${event.reason}` : ''}`,
        });

        if (options.signal?.aborted || event.code === 1000) {
          finalizeResolve();
          return;
        }

        finalizeReject(
          new Error(`socket closed for ${subscription} with code ${event.code}`),
        );
      });
    });
  });
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

  return `${subscription}:${crypto
    .createHash('sha1')
    .update(JSON.stringify(item))
    .digest('hex')}`;
}

function normalizeTimestamp(value: number | null): number {
  if (value === null) {
    return Math.floor(Date.now() / 1000);
  }
  return value < 10_000_000_000 ? value : Math.floor(value / 1000);
}

function buildSubscriptionWsUrl(
  subscription: DexScreenerSubscription,
  limit?: number,
): string {
  const url = new URL(SUBSCRIPTION_ENDPOINTS[subscription], DEXSCREENER_WS_BASE);
  if (typeof limit === 'number' && limit > 0) {
    url.searchParams.set('limit', String(limit));
  }
  return url.toString();
}

function coalesce(...values: unknown[]): string | null {
  for (const value of values) {
    const parsed = asString(value);
    if (parsed) return parsed;
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
  return current;
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

function emitStatus(
  handler: WatchDexSubscriptionsOptions['onStatus'],
  event: DexStreamStatusEvent,
): void {
  handler?.(event);
}

async function readMessageText(data: unknown): Promise<string | null> {
  if (typeof data === 'string') {
    return data;
  }
  if (data instanceof ArrayBuffer) {
    return new TextDecoder().decode(data);
  }
  if (ArrayBuffer.isView(data)) {
    return new TextDecoder().decode(data);
  }
  if (typeof Blob !== 'undefined' && data instanceof Blob) {
    return await data.text();
  }
  return null;
}

function safeClose(socket: WebSocket, code: number, reason: string): void {
  if (
    socket.readyState === WebSocket.CLOSING ||
    socket.readyState === WebSocket.CLOSED
  ) {
    return;
  }

  try {
    socket.close(code, reason);
  } catch {
    socket.close();
  }
}

async function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  if (signal?.aborted) {
    return;
  }

  await new Promise<void>(resolve => {
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', handleAbort);
      resolve();
    }, ms);

    const handleAbort = (): void => {
      clearTimeout(timer);
      signal?.removeEventListener('abort', handleAbort);
      resolve();
    };

    signal?.addEventListener('abort', handleAbort, { once: true });
  });
}

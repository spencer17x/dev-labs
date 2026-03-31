import crypto from 'node:crypto';

import type { SignalEvent } from '@/lib/types';
import { signalTradeConfig } from '@/lib/runtime/config';

const DEXSCREENER_API_BASE = 'https://api.dexscreener.com';
const DEXSCREENER_WS_BASE = 'wss://api.dexscreener.com';
const MIN_STALE_TIMEOUT_MS = 15_000;

export const ALL_DEX_SUBSCRIPTIONS = [
  'token_profiles_latest',
  'community_takeovers_latest',
  'ads_latest',
  'token_boosts_latest',
  'token_boosts_top',
] as const;

export type DexScreenerSubscription = (typeof ALL_DEX_SUBSCRIPTIONS)[number];

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

  const response = await fetch(url, {
    headers: {
      Accept: 'application/json',
    },
    next: { revalidate: 0 },
    signal: AbortSignal.timeout(signalTradeConfig.dexscreener.requestTimeoutSec * 1000),
  });
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
  payload: unknown,
  limit?: number,
): SignalEvent[] {
  const items = extractItems(payload).slice(0, limit && limit > 0 ? limit : undefined);
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
  item: Record<string, unknown>,
): SignalEvent {
  const chainId = coalesce(item.chainId, item.chain, item.network);
  const tokenAddress = coalesce(
    item.tokenAddress,
    item.address,
    deepGet(item, 'token', 'address'),
  );

  return {
    id: buildEventId(subscription, chainId, tokenAddress, item),
    source: 'dexscreener',
    subtype: subscription,
    timestamp: normalizeTimestamp(
      coalesceNumber(
        item.paymentTimestamp,
        item.timestamp,
        item.createdAt,
        item.updatedAt,
      ),
    ),
    chain: chainId,
    token: {
      symbol: coalesce(item.symbol, deepGet(item, 'token', 'symbol')),
      name: coalesce(item.tokenName, item.name, deepGet(item, 'token', 'name')),
      address: tokenAddress,
    },
    author: buildAuthor(item),
    text: coalesce(item.description, item.title),
    metrics: extractMetrics(item),
    raw: item,
    metadata: {
      subscription,
      dexscreener: {
        url: item.url,
        icon: item.icon,
        header: item.header,
        description: item.description,
        links: extractLinks(item.links),
      },
    },
  };
}

function buildAuthor(
  item: Record<string, unknown>,
): SignalEvent['author'] {
  const authorName = coalesce(item.author, item.projectOwner, item.project);
  if (!authorName) {
    return null;
  }
  return {
    display_name: authorName,
  };
}

function extractMetrics(item: Record<string, unknown>): Record<string, number> {
  const metrics: Record<string, number> = {};
  const candidates: Record<string, unknown> = {
    amount: item.amount,
    totalAmount: item.totalAmount,
    activeBoosts: deepGet(item, 'boosts', 'active'),
  };

  for (const [key, value] of Object.entries(candidates)) {
    const parsed = asNumber(value);
    if (parsed !== null) {
      metrics[key] = parsed;
    }
  }

  return metrics;
}

function extractItems(payload: unknown): Array<Record<string, unknown>> {
  if (Array.isArray(payload)) {
    return payload.filter(isObject);
  }

  if (isObject(payload)) {
    const data = payload.data;
    if (Array.isArray(data)) {
      return data.filter(isObject);
    }
    if (isObject(data)) {
      return [data];
    }
    return [payload];
  }

  return [];
}

function extractLinks(value: unknown): Array<Record<string, string>> {
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

function buildEventId(
  subscription: DexScreenerSubscription,
  chainId: string | null,
  tokenAddress: string | null,
  item: Record<string, unknown>,
): string {
  const stableBits = [
    subscription,
    chainId ?? '',
    tokenAddress ?? '',
    String(item.amount ?? ''),
    String(item.totalAmount ?? ''),
    String(item.paymentTimestamp ?? ''),
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
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
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

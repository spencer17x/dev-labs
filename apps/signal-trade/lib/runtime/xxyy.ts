import type { SignalContextXXYY } from '@/lib/types';
import { signalTradeConfig } from '@/lib/runtime/config';

const XXYY_BASE_URL = 'https://www.xxyy.io';
const XXYY_FOLLOW_BASE_URL = 'https://amazon-ga.xxyy.io';

type XXYYSnapshot = Record<string, unknown>;

export async function buildXXYYContext(
  tokenAddress: string,
  chain: string,
): Promise<SignalContextXXYY> {
  const normalizedChain = chain || 'sol';
  let snapshot: XXYYSnapshot = {};
  let pairInfo: Record<string, unknown> = {};
  let statInfo: Record<string, unknown> = {};
  let kolHolders: Array<Record<string, unknown>> = [];
  let followHolders: Array<Record<string, unknown>> = [];

  try {
    pairInfo = await fetchPairInfo(tokenAddress, normalizedChain);
  } catch {
    snapshot = await findTokenSnapshot(tokenAddress, normalizedChain);
  }

  try {
    statInfo = await fetchHolderStatInfo(tokenAddress, normalizedChain);
  } catch {
    // Keep degraded context.
  }

  const pairAddress =
    asString(
      deepGet(pairInfo, 'data', 'launchPlatform', 'launchedPair'),
    ) ||
    asString(snapshot.pairAddress) ||
    tokenAddress;

  try {
    kolHolders = await fetchKolHolders(tokenAddress, pairAddress, normalizedChain);
  } catch {
    // Keep degraded context.
  }

  try {
    followHolders = await fetchFollowHolders(tokenAddress, pairAddress, normalizedChain);
  } catch {
    // Keep degraded context.
  }

  return normalizeXXYYContext(
    snapshot,
    isObject(statInfo.data) ? statInfo.data : {},
    isObject(pairInfo.data) ? pairInfo.data : {},
    kolHolders,
    followHolders,
  );
}

async function fetchTrending(chain: string): Promise<XXYYSnapshot[]> {
  const response = await fetch(`${XXYY_BASE_URL}/api/data/list/trending`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      referer: XXYY_BASE_URL,
      'x-chain': chain,
    },
    body: JSON.stringify({ period: '1M', category: '' }),
    next: { revalidate: 0 },
    signal: AbortSignal.timeout(30_000),
  });

  if (!response.ok) {
    throw new Error(`xxyy trending request failed: ${response.status}`);
  }

  const payload = (await response.json()) as Record<string, unknown>;
  return Array.isArray(payload.data)
    ? payload.data.filter(isObject)
    : [];
}

async function findTokenSnapshot(
  tokenAddress: string,
  chain: string,
): Promise<XXYYSnapshot> {
  const items = await fetchTrending(chain);
  const normalized = tokenAddress.trim().toLowerCase();
  return (
    items.find(item => asString(item.tokenAddress)?.toLowerCase() === normalized) || {}
  );
}

async function fetchPairInfo(
  pairAddress: string,
  chain: string,
): Promise<Record<string, unknown>> {
  return requestJson(`${XXYY_BASE_URL}/api/data/pair/info`, {
    headers: {
      accept: 'application/json, text/plain, */*',
      origin: XXYY_BASE_URL,
      referer: `${XXYY_BASE_URL}/${chain}/${pairAddress}`,
      'user-agent':
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
      'x-chain': chain,
      'x-language': 'zh',
      'x-version': '1',
    },
    params: {
      pairAddress,
      baseOnly: '0',
    },
  });
}

async function fetchHolderStatInfo(
  mint: string,
  chain: string,
): Promise<Record<string, unknown>> {
  const headers = buildProtectedHeaders(chain);
  return requestJson(`${XXYY_FOLLOW_BASE_URL}/api/data/holders/statInfo`, {
    headers,
    params: {
      mint,
      onlyTotal: '0',
    },
  });
}

async function fetchKolHolders(
  mint: string,
  pair: string,
  chain: string,
): Promise<Array<Record<string, unknown>>> {
  const response = await requestJson(`${XXYY_BASE_URL}/api/data/holders/kol`, {
    headers: {
      accept: 'application/json, text/plain, */*',
      referer: `${XXYY_BASE_URL}/${chain}/${pair}`,
      'x-chain': chain,
    },
    params: { mint, pair },
  });

  return Array.isArray(response.data) ? response.data.filter(isObject) : [];
}

async function fetchFollowHolders(
  mint: string,
  pair: string,
  chain: string,
): Promise<Array<Record<string, unknown>>> {
  const response = await requestJson(`${XXYY_FOLLOW_BASE_URL}/api/data/holders/follow`, {
    headers: buildProtectedHeaders(chain),
    params: { mint, pair },
  });

  return Array.isArray(response.data) ? response.data.filter(isObject) : [];
}

async function requestJson(
  input: string,
  {
    headers,
    params,
  }: {
    headers: Record<string, string>;
    params?: Record<string, string>;
  },
): Promise<Record<string, unknown>> {
  const url = new URL(input);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      url.searchParams.set(key, value);
    }
  }

  if (signalTradeConfig.xxyyAuth.cookie) {
    headers.cookie = signalTradeConfig.xxyyAuth.cookie;
  }

  const response = await fetch(url, {
    headers,
    next: { revalidate: 0 },
    signal: AbortSignal.timeout(30_000),
  });

  if (!response.ok) {
    throw new Error(`xxyy request failed: ${response.status}`);
  }

  return (await response.json()) as Record<string, unknown>;
}

function buildProtectedHeaders(chain: string): Record<string, string> {
  const headers: Record<string, string> = {
    accept: 'application/json, text/plain, */*',
    origin: XXYY_BASE_URL,
    referer: `${XXYY_BASE_URL}/`,
    'user-agent':
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
    'x-chain': chain,
    'x-language': 'zh',
    'x-version': '1',
  };

  if (signalTradeConfig.xxyyAuth.authorization) {
    headers.authorization = signalTradeConfig.xxyyAuth.authorization;
  }
  if (signalTradeConfig.xxyyAuth.infoToken) {
    headers['x-info-token'] = signalTradeConfig.xxyyAuth.infoToken;
  }

  return headers;
}

function normalizeXXYYContext(
  snapshot: XXYYSnapshot,
  statInfo: Record<string, unknown>,
  pairInfo: Record<string, unknown>,
  kolHolders: Array<Record<string, unknown>>,
  followHolders: Array<Record<string, unknown>>,
): SignalContextXXYY {
  const priceInfo = objectValue(pairInfo.priceInfo);
  const tokenInfo = objectValue(pairInfo.tokenInfo);
  const linkInfo = objectValue(tokenInfo.linkInfo);
  const holderInfo = objectValue(pairInfo.holderInfo);
  const security = objectValue(pairInfo.securityInfo);
  const auditInfo = objectValue(pairInfo.assistInfo);
  const launchPlatform = objectValue(pairInfo.launchPlatform);
  const pairDetails = objectValue(pairInfo.pairInfo);
  const snapshotLinks = objectValue(snapshot.links);

  return {
    market_cap: asNumber(priceInfo.marketCapUSD) ?? asNumber(snapshot.marketCapUSD),
    holder_count:
      asInteger(statInfo.totalHolders) ??
      asInteger(holderInfo.total) ??
      asInteger(snapshot.holders),
    price_usd: asNumber(priceInfo.priceUSD) ?? asNumber(snapshot.priceUSD),
    volume:
      asNumber(deepGet(pairInfo, 'tradeInfo', 'volume24HUSD')) ??
      asNumber(snapshot.volume),
    liquidity:
      asNumber(pairDetails.liquidityUSD) ?? asNumber(snapshot.liquid),
    buy_count: asInteger(snapshot.buyCount),
    sell_count: asInteger(snapshot.sellCount),
    follow_buy_count:
      asInteger(statInfo.followedHolders) ?? countFollowBuyers(followHolders),
    kol_buy_count:
      asInteger(statInfo.kolHolders) ?? countKolBuyers(kolHolders),
    follow_or_kol_buy_count:
      (asInteger(statInfo.followedHolders) ?? countFollowBuyers(followHolders)) +
      (asInteger(statInfo.kolHolders) ?? countKolBuyers(kolHolders)),
    follow_addresses: extractUniqueValues(followHolders, 'address'),
    kol_addresses: extractUniqueValues(kolHolders, 'address'),
    follow_names: extractUniqueValues(followHolders, 'name'),
    kol_names: extractUniqueValues(kolHolders, 'name'),
    insider_holder_count: asInteger(statInfo.insiderHolders),
    project_twitter_url: asString(linkInfo.x) ?? asString(snapshotLinks.x),
    project_telegram_url: asString(linkInfo.tg) ?? asString(snapshotLinks.tg),
    security: {
      honeypot: asBoolean(deepGet(security, 'honeyPot', 'value')),
      top_holder_percent: asNumber(deepGet(security, 'topHolder', 'value')),
    },
    audit: {
      dev_hold_percent: asNumber(auditInfo.devHp),
      snipers: asInteger(auditInfo.snipers),
      dex_paid: asBoolean(auditInfo.dexPaid),
    },
    launch_platform: {
      name: asString(launchPlatform.name),
      completed: asBoolean(launchPlatform.completed),
      launched_pair: asString(launchPlatform.launchedPair),
    },
    holder_stats: statInfo,
    pair_info: pairInfo,
    raw: snapshot,
    follow_holders: followHolders,
    kol_holders: kolHolders,
  };
}

function countKolBuyers(items: Array<Record<string, unknown>>): number {
  let count = 0;
  for (const item of items) {
    const buyCount = asInteger(item.buyCount);
    if (buyCount !== null) {
      if (buyCount > 0) {
        count += 1;
      }
      continue;
    }
    if ((asNumber(item.holdAmount) ?? 0) > 0) {
      count += 1;
    }
  }
  return count;
}

function countFollowBuyers(items: Array<Record<string, unknown>>): number {
  let count = 0;
  for (const item of items) {
    const buyCount = asInteger(item.buyCount);
    if (buyCount !== null) {
      if (buyCount > 0) {
        count += 1;
      }
      continue;
    }
    const holdAmount = asNumber(item.holdAmount);
    if (holdAmount === null || holdAmount > 0) {
      count += 1;
    }
  }
  return count;
}

function extractUniqueValues(
  items: Array<Record<string, unknown>>,
  key: string,
): string[] {
  const values = new Set<string>();
  const results: string[] = [];

  for (const item of items) {
    const rawValue = asString(item[key]);
    if (!rawValue) {
      continue;
    }
    const normalized = rawValue.toLowerCase();
    if (values.has(normalized)) {
      continue;
    }
    values.add(normalized);
    results.push(rawValue);
  }

  return results;
}

function deepGet(value: unknown, ...keys: string[]): unknown {
  let current = value;
  for (const key of keys) {
    if (!isObject(current)) {
      return null;
    }
    current = current[key];
  }
  return current;
}

function objectValue(value: unknown): Record<string, unknown> {
  return isObject(value) ? value : {};
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
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

function asInteger(value: unknown): number | null {
  const parsed = asNumber(value);
  return parsed === null ? null : Math.trunc(parsed);
}

function asBoolean(value: unknown): boolean | null {
  if (typeof value === 'boolean') {
    return value;
  }
  if (value === null || value === undefined || value === '') {
    return null;
  }
  return Boolean(value);
}

function isObject(value: unknown): value is Record<string, any> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

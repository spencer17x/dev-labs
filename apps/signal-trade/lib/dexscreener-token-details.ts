import type {
  DexScreenerPairRaw,
  DexScreenerSocialRaw,
  DexScreenerTokenRefRaw,
  DexScreenerTokensByChainResponse,
  DexScreenerWebsiteRaw,
} from './dexscreener-api-types';

const DEXSCREENER_API_BASE = 'https://api.dexscreener.com';
const DEXSCREENER_TOKEN_DETAILS_TIMEOUT_MS = 12_000;

export type DexTokenRef = {
  address: string | null;
  name: string | null;
  symbol: string | null;
};

export type DexTokenSocial = {
  handle: string | null;
  platform: string | null;
  url: string | null;
};

export type DexTokenPairDetails = {
  boostsActive: number | null;
  chainId: string | null;
  dexId: string | null;
  fdv: number | null;
  imageUrl: string | null;
  labels: string[];
  liquidityUsd: number | null;
  marketCap: number | null;
  pairAddress: string | null;
  pairCreatedAt: number | null;
  priceChange24h: number | null;
  priceNative: string | null;
  priceUsd: number | null;
  quoteToken: DexTokenRef;
  socials: DexTokenSocial[];
  token: DexTokenRef;
  txns24hBuys: number | null;
  txns24hSells: number | null;
  url: string | null;
  volume24h: number | null;
  websites: string[];
};

export function buildDexTokenDetailKey(
  chainId: string | null | undefined,
  tokenAddress: string | null | undefined,
): string | null {
  const normalizedChainId = normalizeString(chainId)?.toLowerCase();
  const normalizedTokenAddress = normalizeString(tokenAddress)?.toLowerCase();

  if (!normalizedChainId || !normalizedTokenAddress) {
    return null;
  }

  return `${normalizedChainId}:${normalizedTokenAddress}`;
}

export function chunkDexTokenAddresses(
  tokenAddresses: string[],
  size = 30,
): string[][] {
  const chunks: string[][] = [];

  for (let index = 0; index < tokenAddresses.length; index += size) {
    chunks.push(tokenAddresses.slice(index, index + size));
  }

  return chunks;
}

export async function fetchDexTokenDetailsByChain(
  chainId: string,
  tokenAddresses: string[],
): Promise<Record<string, DexTokenPairDetails | null>> {
  const normalizedChainId = normalizeString(chainId);
  const normalizedTokenAddresses = Array.from(
    new Set(
      tokenAddresses
        .map(tokenAddress => normalizeString(tokenAddress)?.toLowerCase() ?? '')
        .filter(Boolean),
    ),
  );

  if (!normalizedChainId || normalizedTokenAddresses.length === 0) {
    return {};
  }

  const url = new URL(
    `/tokens/v1/${encodeURIComponent(normalizedChainId)}/${normalizedTokenAddresses.join(',')}`,
    DEXSCREENER_API_BASE,
  );

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), DEXSCREENER_TOKEN_DETAILS_TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      headers: {
        Accept: 'application/json',
      },
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(`dex token detail request failed: ${response.status}`);
    }

    const payload = (await response.json()) as DexScreenerTokensByChainResponse | unknown;
    const pairs = Array.isArray(payload)
      ? (payload.filter(isObject) as DexScreenerPairRaw[])
      : [];

    const detailsByAddress: Record<string, DexTokenPairDetails | null> = {};
    for (const tokenAddress of normalizedTokenAddresses) {
      detailsByAddress[tokenAddress] = pickBestPairDetails(pairs, tokenAddress);
    }

    return detailsByAddress;
  } finally {
    clearTimeout(timer);
  }
}

function pickBestPairDetails(
  pairs: DexScreenerPairRaw[],
  tokenAddress: string,
): DexTokenPairDetails | null {
  const matchingPairs = pairs.filter(pair => {
    const baseAddress = normalizeString(deepGet(pair, 'baseToken', 'address'))?.toLowerCase();
    const quoteAddress = normalizeString(deepGet(pair, 'quoteToken', 'address'))?.toLowerCase();

    return baseAddress === tokenAddress || quoteAddress === tokenAddress;
  });

  if (matchingPairs.length === 0) {
    return null;
  }

  const sortedPairs = [...matchingPairs].sort(comparePairs);
  return normalizePairDetails(sortedPairs[0], tokenAddress);
}

function comparePairs(
  left: DexScreenerPairRaw,
  right: DexScreenerPairRaw,
): number {
  const leftLiquidity = asNumber(deepGet(left, 'liquidity', 'usd')) ?? Number.NEGATIVE_INFINITY;
  const rightLiquidity =
    asNumber(deepGet(right, 'liquidity', 'usd')) ?? Number.NEGATIVE_INFINITY;
  if (leftLiquidity !== rightLiquidity) {
    return rightLiquidity - leftLiquidity;
  }

  const leftVolume = asNumber(deepGet(left, 'volume', 'h24')) ?? Number.NEGATIVE_INFINITY;
  const rightVolume = asNumber(deepGet(right, 'volume', 'h24')) ?? Number.NEGATIVE_INFINITY;
  if (leftVolume !== rightVolume) {
    return rightVolume - leftVolume;
  }

  const leftMarketCap = asNumber(left.marketCap) ?? Number.NEGATIVE_INFINITY;
  const rightMarketCap = asNumber(right.marketCap) ?? Number.NEGATIVE_INFINITY;
  if (leftMarketCap !== rightMarketCap) {
    return rightMarketCap - leftMarketCap;
  }

  const leftCreatedAt = normalizeTimestamp(asNumber(left.pairCreatedAt));
  const rightCreatedAt = normalizeTimestamp(asNumber(right.pairCreatedAt));
  return rightCreatedAt - leftCreatedAt;
}

function normalizePairDetails(
  pair: DexScreenerPairRaw,
  tokenAddress: string,
): DexTokenPairDetails {
  const baseAddress = normalizeString(deepGet(pair, 'baseToken', 'address'))?.toLowerCase();
  const isBaseToken = baseAddress === tokenAddress;

  return {
    boostsActive: asInteger(deepGet(pair, 'boosts', 'active')),
    chainId: normalizeString(pair.chainId),
    dexId: normalizeString(pair.dexId),
    fdv: asNumber(pair.fdv),
    imageUrl: normalizeString(deepGet(pair, 'info', 'imageUrl')),
    labels: asStringArray(pair.labels),
    liquidityUsd: asNumber(deepGet(pair, 'liquidity', 'usd')),
    marketCap: asNumber(pair.marketCap),
    pairAddress: normalizeString(pair.pairAddress),
    pairCreatedAt: asInteger(pair.pairCreatedAt),
    priceChange24h: asNumber(deepGet(pair, 'priceChange', 'h24')),
    priceNative: normalizeString(pair.priceNative),
    priceUsd: asNumber(pair.priceUsd),
    quoteToken: normalizeTokenRef(
      isBaseToken ? deepGet(pair, 'quoteToken') : deepGet(pair, 'baseToken'),
    ),
    socials: normalizeSocials(deepGet(pair, 'info', 'socials')),
    token: normalizeTokenRef(
      isBaseToken ? deepGet(pair, 'baseToken') : deepGet(pair, 'quoteToken'),
    ),
    txns24hBuys: asInteger(deepGet(pair, 'txns', 'h24', 'buys')),
    txns24hSells: asInteger(deepGet(pair, 'txns', 'h24', 'sells')),
    url: normalizeString(pair.url),
    volume24h: asNumber(deepGet(pair, 'volume', 'h24')),
    websites: normalizeWebsites(deepGet(pair, 'info', 'websites')),
  };
}

function normalizeTokenRef(value: DexScreenerTokenRefRaw | unknown): DexTokenRef {
  return {
    address: normalizeString(isObject(value) ? value.address : null),
    name: normalizeString(isObject(value) ? value.name : null),
    symbol: normalizeString(isObject(value) ? value.symbol : null),
  };
}

function normalizeWebsites(value: DexScreenerWebsiteRaw[] | unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map(item => (isObject(item) ? normalizeString(item.url) : null))
    .filter((item): item is string => Boolean(item));
}

function normalizeSocials(value: DexScreenerSocialRaw[] | unknown): DexTokenSocial[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map(item => {
      if (!isObject(item)) {
        return null;
      }

      const platform = normalizeString(item.platform);
      const handle = normalizeString(item.handle);

      if (!platform && !handle) {
        return null;
      }

      return {
        handle,
        platform,
        url: buildSocialUrl(platform, handle),
      } satisfies DexTokenSocial;
    })
    .filter((item): item is DexTokenSocial => item !== null);
}

function buildSocialUrl(
  platform: string | null,
  handle: string | null,
): string | null {
  if (!handle) {
    return null;
  }

  if (/^https?:\/\//i.test(handle)) {
    return handle;
  }

  const normalizedPlatform = platform?.toLowerCase() ?? '';
  const normalizedHandle = handle.replace(/^@/, '');

  if (normalizedPlatform === 'twitter' || normalizedPlatform === 'x') {
    return `https://x.com/${normalizedHandle}`;
  }

  if (normalizedPlatform === 'telegram' || normalizedPlatform === 'tg') {
    return `https://t.me/${normalizedHandle.replace(/^\//, '')}`;
  }

  return null;
}

function normalizeTimestamp(value: number | null): number {
  if (value === null) {
    return 0;
  }

  return value < 10_000_000_000 ? value * 1000 : value;
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

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map(item => normalizeString(item))
    .filter((item): item is string => Boolean(item));
}

function normalizeString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function deepGet(
  payload: unknown,
  ...keys: string[]
): unknown {
  let current = payload;
  for (const key of keys) {
    if (!isObject(current)) {
      return null;
    }
    current = current[key];
  }
  return current;
}

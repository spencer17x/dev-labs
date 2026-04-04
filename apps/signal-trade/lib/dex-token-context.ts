type SignalContextTokenLike = {
  address?: string | null;
  chain?: string | null;
  name?: string | null;
  symbol?: string | null;
};

type SignalContextSocialLike = {
  handle?: string | null;
  platform?: string | null;
  url?: string | null;
};

type SignalContextDexscreenerLike = {
  fdv?: number | null;
  icon?: string | null;
  imageUrl?: string | null;
  liquidityUsd?: number | null;
  links?: Array<Record<string, unknown>>;
  marketCap?: number | null;
  priceUsd?: number | null;
  socials?: SignalContextSocialLike[];
  url?: string | null;
  websites?: string[];
};

export type SignalContextLike = {
  dexscreener?: SignalContextDexscreenerLike;
  token?: SignalContextTokenLike;
  [key: string]: unknown;
};

export type DexTokenPairDetailsLike = {
  fdv?: number | null;
  imageUrl?: string | null;
  liquidityUsd?: number | null;
  marketCap?: number | null;
  priceUsd?: number | null;
  socials?: SignalContextSocialLike[];
  token?: SignalContextTokenLike;
  url?: string | null;
  websites?: string[];
};

export function mergeSignalContextWithDexTokenDetail(
  context: SignalContextLike,
  detail: DexTokenPairDetailsLike | null,
): SignalContextLike {
  if (!detail) {
    return context;
  }

  const currentToken = context.token ?? {};
  const currentDexscreener = context.dexscreener ?? {};

  return {
    ...context,
    token: {
      ...currentToken,
      address: firstString(currentToken.address, detail.token?.address),
      chain: firstString(currentToken.chain),
      name: firstString(currentToken.name, detail.token?.name),
      symbol: firstString(currentToken.symbol, detail.token?.symbol),
    },
    dexscreener: {
      ...currentDexscreener,
      fdv: firstNumber(currentDexscreener.fdv, detail.fdv),
      imageUrl: firstString(
        currentDexscreener.imageUrl,
        detail.imageUrl,
        currentDexscreener.icon,
      ),
      liquidityUsd: firstNumber(
        currentDexscreener.liquidityUsd,
        detail.liquidityUsd,
      ),
      marketCap: firstNumber(currentDexscreener.marketCap, detail.marketCap),
      priceUsd: firstNumber(currentDexscreener.priceUsd, detail.priceUsd),
      socials: mergeSocials(currentDexscreener.socials, detail.socials),
      url: firstString(currentDexscreener.url, detail.url),
      websites: mergeStrings(currentDexscreener.websites, detail.websites),
    },
  };
}

function mergeStrings(
  current: string[] | undefined,
  incoming: string[] | undefined,
): string[] {
  const merged: string[] = [];
  const seen = new Set<string>();

  for (const value of [...(current ?? []), ...(incoming ?? [])]) {
    if (!isNonEmptyString(value)) {
      continue;
    }

    const normalized = value.trim();
    const key = normalized.toLowerCase();
    if (seen.has(key)) {
      continue;
    }

    seen.add(key);
    merged.push(normalized);
  }

  return merged;
}

function mergeSocials(
  current: SignalContextSocialLike[] | undefined,
  incoming: SignalContextSocialLike[] | undefined,
): SignalContextSocialLike[] {
  const merged: SignalContextSocialLike[] = [];
  const seen = new Set<string>();

  for (const social of [...(current ?? []), ...(incoming ?? [])]) {
    const handle = normalizeString(social?.handle);
    const platform = normalizeString(social?.platform);
    const url = normalizeString(social?.url);

    if (!handle && !platform && !url) {
      continue;
    }

    const key = (url ?? `${platform ?? ''}:${handle ?? ''}`).toLowerCase();
    if (seen.has(key)) {
      continue;
    }

    seen.add(key);
    merged.push({
      handle,
      platform,
      url,
    });
  }

  return merged;
}

function firstNumber(...values: Array<number | null | undefined>): number | null {
  for (const value of values) {
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value;
    }
  }

  return null;
}

function firstString(...values: Array<string | null | undefined>): string | null {
  for (const value of values) {
    if (isNonEmptyString(value)) {
      return value.trim();
    }
  }

  return null;
}

function normalizeString(value: string | null | undefined): string | null {
  return isNonEmptyString(value) ? value.trim() : null;
}

function isNonEmptyString(value: string | null | undefined): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

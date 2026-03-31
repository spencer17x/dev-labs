import type {
  SignalContext,
  SignalContextDexscreener,
  SignalEvent,
} from '@/lib/types';
import {
  extractTwitterUsername,
  findSocialLink,
} from '@/lib/runtime/twitter';

export async function enrichSignalEvent(event: SignalEvent): Promise<SignalContext> {
  const raw = isObject(event.raw) ? event.raw : {};
  const links = normalizeLinks(
    Array.isArray(deepGet(event.metadata, 'dexscreener', 'links'))
      ? (deepGet(event.metadata, 'dexscreener', 'links') as Array<Record<string, unknown>>)
      : [],
  );
  const twitterUrl = findSocialLink(links, ['twitter', 'x']);
  const telegramUrl = findSocialLink(links, ['telegram']);
  const twitterUsername = extractTwitterUsername(twitterUrl);

  const context: SignalContext = {
    token: {
      chain: event.chain,
      address: event.token.address,
      symbol: event.token.symbol,
      name: event.token.name,
    },
    dexscreener: {
      source: event.subtype,
      paid: event.subtype === 'token_profiles_latest',
      timestamp: event.timestamp,
      url: asString(deepGet(event.metadata, 'dexscreener', 'url')) ?? asString(raw.url),
      icon: asString(deepGet(event.metadata, 'dexscreener', 'icon')) ?? asString(raw.icon),
      imageUrl:
        asString(raw.imageUrl) ??
        asString(raw.image) ??
        asString(deepGet(raw, 'token', 'imageUrl')) ??
        asString(deepGet(event.metadata, 'dexscreener', 'icon')),
      header:
        asString(deepGet(event.metadata, 'dexscreener', 'header')) ??
        asString(raw.header) ??
        asString(raw.title),
      description:
        asString(deepGet(event.metadata, 'dexscreener', 'description')) ??
        asString(raw.description) ??
        asString(event.text),
      priceUsd: readNumber(raw.priceUsd, raw.price_usd, deepGet(raw, 'price', 'usd')),
      liquidityUsd: readNumber(
        raw.liquidityUsd,
        raw.liquidity_usd,
        deepGet(raw, 'liquidity', 'usd'),
      ),
      marketCap: readNumber(raw.marketCap, raw.market_cap),
      fdv: readNumber(raw.fdv, raw.fdv_usd),
      websites: extractWebsites(links),
      socials: extractSocials(links),
      links,
    },
    xxyy: {},
    twitter: {
      profile_url: twitterUrl,
      username: twitterUsername,
      community_count: null,
      followers_count: null,
      friends_count: null,
      statuses_count: null,
    },
  };

  if (!context.token?.symbol) {
    context.token = {
      ...context.token,
      symbol: asString(raw.symbol) ?? asString(deepGet(raw, 'token', 'symbol')),
    };
  }

  if (!context.token?.name) {
    context.token = {
      ...context.token,
      name:
        asString(raw.tokenName) ??
        asString(raw.name) ??
        asString(deepGet(raw, 'token', 'name')),
    };
  }

  if (telegramUrl && context.xxyy && !context.xxyy.project_telegram_url) {
    context.xxyy.project_telegram_url = telegramUrl;
  }

  return context;
}

function deepGet(payload: unknown, ...keys: string[]): unknown {
  let current = payload;
  for (const key of keys) {
    if (!current || typeof current !== 'object' || Array.isArray(current)) {
      return null;
    }
    current = (current as Record<string, unknown>)[key];
  }
  return current;
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

function readNumber(...values: unknown[]): number | null {
  for (const value of values) {
    const parsed = asNumber(value);
    if (parsed !== null) {
      return parsed;
    }
  }
  return null;
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

function normalizeLinks(
  value: Array<Record<string, unknown>>,
): Array<Record<string, unknown>> {
  return value.filter(isObject);
}

function extractWebsites(
  links: Array<Record<string, unknown>>,
): string[] {
  return links
    .filter(link => {
      const type = asString(link.type)?.toLowerCase() ?? '';
      return type === 'website' || type === 'site';
    })
    .map(link => asString(link.url))
    .filter((value): value is string => Boolean(value));
}

function extractSocials(
  links: Array<Record<string, unknown>>,
): SignalContextDexscreener['socials'] {
  const socials: SignalContextDexscreener['socials'] = [];

  for (const link of links) {
    const platform = asString(link.type)?.toLowerCase() ?? null;
    const url = asString(link.url);
    if (!platform || !url) {
      continue;
    }

    socials.push({
      handle:
        platform === 'twitter' || platform === 'x'
          ? extractTwitterUsername(url)
          : null,
      platform,
      url,
    });
  }

  return socials;
}

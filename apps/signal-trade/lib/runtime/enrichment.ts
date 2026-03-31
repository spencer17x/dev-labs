import {
  fetchDexTokenDetailsByChain,
  type DexTokenPairDetails,
} from '@/lib/dexscreener-token-details';
import type { SignalContext, SignalEvent } from '@/lib/types';
import {
  fetchTwitterProfileMetrics,
  extractTwitterUsername,
  findSocialLink,
} from '@/lib/runtime/twitter';
import { buildXXYYContext } from '@/lib/runtime/xxyy';

export async function enrichSignalEvent(event: SignalEvent): Promise<SignalContext> {
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
      url: asString(deepGet(event.metadata, 'dexscreener', 'url')),
      icon: asString(deepGet(event.metadata, 'dexscreener', 'icon')),
      imageUrl: null,
      header: asString(deepGet(event.metadata, 'dexscreener', 'header')),
      description: asString(deepGet(event.metadata, 'dexscreener', 'description')),
      priceUsd: null,
      liquidityUsd: null,
      marketCap: null,
      fdv: null,
      websites: [],
      socials: [],
      links:
        (Array.isArray(deepGet(event.metadata, 'dexscreener', 'links'))
          ? (deepGet(event.metadata, 'dexscreener', 'links') as Array<Record<string, unknown>>)
          : []) || [],
    },
    xxyy: {},
    twitter: {},
  };

  if (event.source === 'dexscreener' && event.token.address) {
    try {
      const details = await fetchDexTokenDetails(
        event.chain ?? null,
        event.token.address,
      );
      if (details) {
        context.token = {
          chain: context.token?.chain ?? details.chainId ?? event.chain,
          address:
            context.token?.address ?? details.token.address ?? event.token.address,
          symbol: context.token?.symbol ?? details.token.symbol ?? event.token.symbol,
          name: context.token?.name ?? details.token.name ?? event.token.name,
        };
        context.dexscreener = {
          ...context.dexscreener,
          url: context.dexscreener?.url || details.url || null,
          icon: context.dexscreener?.icon || details.imageUrl || null,
          imageUrl: details.imageUrl,
          priceUsd: details.priceUsd,
          liquidityUsd: details.liquidityUsd,
          marketCap: details.marketCap,
          fdv: details.fdv,
          websites: [...details.websites],
          socials: details.socials.map(item => ({ ...item })),
        };
      }
    } catch {
      // Keep degraded context when token detail lookup fails.
    }

    try {
      context.xxyy = await buildXXYYContext(event.token.address, event.chain || 'sol');
    } catch {
      context.xxyy = {};
    }
  }

  const links = context.dexscreener?.links ?? [];
  const twitterUrl =
    findSocialLink(links, ['twitter', 'x']) ||
    asString(context.xxyy?.project_twitter_url) ||
    null;
  const telegramUrl = findSocialLink(links, ['telegram']);

  if (telegramUrl && context.xxyy && !context.xxyy.project_telegram_url) {
    context.xxyy.project_telegram_url = telegramUrl;
  }

  const username = extractTwitterUsername(twitterUrl);
  const profileMetrics = username
    ? await fetchTwitterProfileMetrics(username)
    : {
        username: null,
        profile_url: null,
        community_count: null,
        followers_count: null,
        friends_count: null,
        statuses_count: null,
      };

  context.twitter = {
    ...profileMetrics,
    profile_url: twitterUrl || profileMetrics.profile_url || null,
    username: username || profileMetrics.username || null,
  };

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

async function fetchDexTokenDetails(
  chainId: string | null,
  tokenAddress: string,
): Promise<DexTokenPairDetails | null> {
  const normalizedTokenAddress = tokenAddress.trim().toLowerCase();
  if (!normalizedTokenAddress) {
    return null;
  }

  for (const candidate of getDexDetailChainCandidates(chainId)) {
    const detailsByAddress = await fetchDexTokenDetailsByChain(candidate, [
      normalizedTokenAddress,
    ]);
    const details = detailsByAddress[normalizedTokenAddress];
    if (details) {
      return details;
    }
  }

  return null;
}

function getDexDetailChainCandidates(chainId: string | null): string[] {
  if (!chainId) {
    return [];
  }

  const normalized = chainId.trim().toLowerCase();
  if (!normalized) {
    return [];
  }

  const aliasMap: Record<string, string[]> = {
    arb: ['arbitrum'],
    arbitrum: ['arb'],
    avax: ['avalanche'],
    avalanche: ['avax'],
    bnb: ['bsc'],
    bsc: ['bnb'],
    eth: ['ethereum'],
    ethereum: ['eth'],
    matic: ['polygon'],
    op: ['optimism'],
    optimism: ['op'],
    polygon: ['matic'],
    sol: ['solana'],
    solana: ['sol'],
  };

  return Array.from(new Set([normalized, ...(aliasMap[normalized] ?? [])]));
}

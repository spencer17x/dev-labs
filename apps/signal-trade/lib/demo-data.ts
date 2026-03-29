import type {
  DashboardFilters,
  NotificationRecord,
  NotificationSummary,
} from '@/lib/types';

export const defaultDashboardFilters: DashboardFilters = {
  search: '',
  watchTerms: '',
  chain: 'all',
  source: 'all',
  strategyId: 'all',
  minHolders: '',
  maxMarketCap: '',
  minCommunityCount: '',
  paidOnly: false,
};

function buildSummary(
  partial: Partial<NotificationSummary>,
): NotificationSummary {
  return {
    paid: Boolean(partial.paid),
    marketCap: partial.marketCap ?? null,
    holderCount: partial.holderCount ?? null,
    communityCount: partial.communityCount ?? null,
    followersCount: partial.followersCount ?? null,
    twitterUsername: partial.twitterUsername ?? null,
    dexscreenerUrl: partial.dexscreenerUrl ?? null,
    telegramUrl: partial.telegramUrl ?? null,
  };
}

export const demoNotifications: NotificationRecord[] = [
  {
    id: 'demo-sol-hyperlane',
    notifiedAt: '2026-03-29T12:04:00.000Z',
    strategyId: 'paid-sol-early',
    channels: ['stdout', 'webhook'],
    message:
      '[paid-sol-early] source=dexscreener.token_profiles_latest token=HYPE market_cap=820000 holders=286 twitter_community=15900',
    event: {
      id: 'dexsol-001',
      source: 'dexscreener',
      subtype: 'token_profiles_latest',
      timestamp: 1774785600000,
      chain: 'sol',
      token: {
        symbol: 'HYPE',
        name: 'Hyperlane Mint',
        address: '9Jr5Y7AQhVf8abL7vHypeMint11111111111111111111',
      },
      text: 'DexScreener paid listing detected.',
    },
    context: {
      token: {
        chain: 'sol',
        symbol: 'HYPE',
        name: 'Hyperlane Mint',
        address: '9Jr5Y7AQhVf8abL7vHypeMint11111111111111111111',
      },
      dexscreener: {
        paid: true,
        url: 'https://dexscreener.com/solana/hypemint',
        description: 'High-conviction Sol listing with concentrated social momentum.',
      },
      xxyy: {
        market_cap: 820000,
        holder_count: 286,
        follow_addresses: ['AVAZvHLR2PcWpDf8BXY4rVxNHYRBytycHkcB5z5QNXYm'],
        kol_names: ['ansem', 'k4ye'],
        project_telegram_url: 'https://t.me/hypemint',
      },
      twitter: {
        username: 'hypemintxyz',
        community_count: 15900,
        followers_count: 22000,
        profile_url: 'https://x.com/hypemintxyz',
      },
    },
    summary: buildSummary({
      paid: true,
      marketCap: 820000,
      holderCount: 286,
      communityCount: 15900,
      followersCount: 22000,
      twitterUsername: 'hypemintxyz',
      dexscreenerUrl: 'https://dexscreener.com/solana/hypemint',
      telegramUrl: 'https://t.me/hypemint',
    }),
  },
  {
    id: 'demo-base-orbit',
    notifiedAt: '2026-03-29T11:46:00.000Z',
    strategyId: 'base-breakout',
    channels: ['stdout'],
    message:
      '[base-breakout] source=dexscreener.token_profiles_latest token=ORBT market_cap=1400000 holders=918 twitter_community=6400',
    event: {
      id: 'dexbase-114',
      source: 'dexscreener',
      subtype: 'token_profiles_latest',
      timestamp: 1774784760000,
      chain: 'base',
      token: {
        symbol: 'ORBT',
        name: 'Orbit Relay',
        address: '0x0rbitrelay0000000000000000000000000000114',
      },
      text: 'Paid Base listing with broad retail spread.',
    },
    context: {
      token: {
        chain: 'base',
        symbol: 'ORBT',
        name: 'Orbit Relay',
        address: '0x0rbitrelay0000000000000000000000000000114',
      },
      dexscreener: {
        paid: true,
        url: 'https://dexscreener.com/base/orbitrelay',
      },
      xxyy: {
        market_cap: 1400000,
        holder_count: 918,
        kol_names: ['miles'],
      },
      twitter: {
        username: 'orbitrelay',
        community_count: 6400,
        followers_count: 8700,
        profile_url: 'https://x.com/orbitrelay',
      },
    },
    summary: buildSummary({
      paid: true,
      marketCap: 1400000,
      holderCount: 918,
      communityCount: 6400,
      followersCount: 8700,
      twitterUsername: 'orbitrelay',
      dexscreenerUrl: 'https://dexscreener.com/base/orbitrelay',
    }),
  },
  {
    id: 'demo-sol-ember',
    notifiedAt: '2026-03-29T11:12:00.000Z',
    strategyId: 'paid-sol-early',
    channels: ['stdout'],
    message:
      '[paid-sol-early] source=dexscreener.token_profiles_latest token=EMBER market_cap=530000 holders=164 twitter_community=9200',
    event: {
      id: 'dexsol-099',
      source: 'dexscreener',
      subtype: 'token_profiles_latest',
      timestamp: 1774782720000,
      chain: 'sol',
      token: {
        symbol: 'EMBER',
        name: 'Ember Circuit',
        address: 'EMBERxx111111111111111111111111111111111111',
      },
      text: 'KOL-linked Sol token with early follow-wallet interest.',
    },
    context: {
      token: {
        chain: 'sol',
        symbol: 'EMBER',
        name: 'Ember Circuit',
        address: 'EMBERxx111111111111111111111111111111111111',
      },
      dexscreener: {
        paid: true,
        url: 'https://dexscreener.com/solana/embercircuit',
      },
      xxyy: {
        market_cap: 530000,
        holder_count: 164,
        follow_addresses: ['FQVbL1FollowWallet1111111111111111111111111'],
        kol_names: ['k4ye'],
      },
      twitter: {
        username: 'embercircuit',
        community_count: 9200,
        followers_count: 12100,
        profile_url: 'https://x.com/embercircuit',
      },
    },
    summary: buildSummary({
      paid: true,
      marketCap: 530000,
      holderCount: 164,
      communityCount: 9200,
      followersCount: 12100,
      twitterUsername: 'embercircuit',
      dexscreenerUrl: 'https://dexscreener.com/solana/embercircuit',
    }),
  },
  {
    id: 'demo-sol-cascade',
    notifiedAt: '2026-03-29T10:35:00.000Z',
    strategyId: 'watch-twitter-surge',
    channels: ['stdout', 'webhook'],
    message:
      '[watch-twitter-surge] source=twitter.profile_update token=CAS market_cap=2600000 holders=2104 twitter_community=48000',
    event: {
      id: 'twitter-021',
      source: 'twitter',
      subtype: 'profile_update',
      timestamp: 1774780500000,
      chain: 'sol',
      token: {
        symbol: 'CAS',
        name: 'Cascade Labs',
        address: 'CAscaDe1111111111111111111111111111111111111',
      },
      author: {
        username: 'cascadelabs',
        display_name: 'Cascade Labs',
      },
      text: 'Community breakout detected from profile polling.',
    },
    context: {
      token: {
        chain: 'sol',
        symbol: 'CAS',
        name: 'Cascade Labs',
        address: 'CAscaDe1111111111111111111111111111111111111',
      },
      dexscreener: {
        paid: false,
      },
      xxyy: {
        market_cap: 2600000,
        holder_count: 2104,
      },
      twitter: {
        username: 'cascadelabs',
        community_count: 48000,
        followers_count: 76300,
        profile_url: 'https://x.com/cascadelabs',
      },
    },
    summary: buildSummary({
      paid: false,
      marketCap: 2600000,
      holderCount: 2104,
      communityCount: 48000,
      followersCount: 76300,
      twitterUsername: 'cascadelabs',
    }),
  },
];

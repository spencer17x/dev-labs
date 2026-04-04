export const DEXSCREENER_LATEST_SUBSCRIPTIONS = [
  'token_profiles_latest',
  'community_takeovers_latest',
  'ads_latest',
  'token_boosts_latest',
  'token_boosts_top',
] as const;

export type DexScreenerLatestSubscription =
  (typeof DEXSCREENER_LATEST_SUBSCRIPTIONS)[number];

export interface DexScreenerLinkRaw {
  label?: string;
  type?: string;
  url?: string;
  [key: string]: unknown;
}

export interface DexScreenerLatestBaseItemRaw {
  chainId?: string;
  description?: string | null;
  header?: string | null;
  icon?: string | null;
  links?: DexScreenerLinkRaw[] | null;
  tokenAddress?: string;
  url?: string;
  [key: string]: unknown;
}

export interface DexScreenerTokenProfileRaw extends DexScreenerLatestBaseItemRaw {}

export interface DexScreenerCommunityTakeoverRaw
  extends DexScreenerLatestBaseItemRaw {
  claimDate?: string;
}

export interface DexScreenerAdRaw {
  chainId?: string;
  date?: string;
  durationHours?: number | null;
  impressions?: number | null;
  tokenAddress?: string;
  type?: string;
  url?: string;
  [key: string]: unknown;
}

export interface DexScreenerTokenBoostRaw
  extends DexScreenerLatestBaseItemRaw {
  amount?: number;
  totalAmount?: number;
}

export type DexScreenerLatestItemBySubscription = {
  ads_latest: DexScreenerAdRaw;
  community_takeovers_latest: DexScreenerCommunityTakeoverRaw;
  token_boosts_latest: DexScreenerTokenBoostRaw;
  token_boosts_top: DexScreenerTokenBoostRaw;
  token_profiles_latest: DexScreenerTokenProfileRaw;
};

export type DexScreenerLatestItemRaw =
  DexScreenerLatestItemBySubscription[DexScreenerLatestSubscription];

export interface DexScreenerLatestWsEnvelopeRaw<
  TItem extends DexScreenerLatestItemRaw = DexScreenerLatestItemRaw,
> {
  data?: TItem[];
  limit?: number;
  [key: string]: unknown;
}

type OneOrMany<T> = T | T[];

export type DexScreenerLatestRestResponseBySubscription = {
  ads_latest: DexScreenerAdRaw[];
  community_takeovers_latest: DexScreenerCommunityTakeoverRaw[];
  token_boosts_latest: OneOrMany<DexScreenerTokenBoostRaw>;
  token_boosts_top: OneOrMany<DexScreenerTokenBoostRaw>;
  token_profiles_latest: OneOrMany<DexScreenerTokenProfileRaw>;
};

export type DexScreenerLatestRestResponse<
  TSubscription extends DexScreenerLatestSubscription = DexScreenerLatestSubscription,
> = DexScreenerLatestRestResponseBySubscription[TSubscription];

export type DexScreenerLatestWsResponse<
  TSubscription extends DexScreenerLatestSubscription = DexScreenerLatestSubscription,
> = DexScreenerLatestWsEnvelopeRaw<DexScreenerLatestItemBySubscription[TSubscription]>;

export type DexScreenerLatestPayload<
  TSubscription extends DexScreenerLatestSubscription = DexScreenerLatestSubscription,
> =
  | DexScreenerLatestRestResponse<TSubscription>
  | DexScreenerLatestWsResponse<TSubscription>;

export interface DexScreenerOrdersPathParams {
  chainId: string;
  tokenAddress: string;
}

export type DexScreenerOrderType =
  | 'tokenProfile'
  | 'communityTakeover'
  | 'tokenAd'
  | 'trendingBarAd';

export type DexScreenerOrderStatus =
  | 'processing'
  | 'cancelled'
  | 'on-hold'
  | 'approved'
  | 'rejected';

export interface DexScreenerOrderRaw {
  paymentTimestamp?: number;
  status?: DexScreenerOrderStatus;
  type?: DexScreenerOrderType;
  [key: string]: unknown;
}

export type DexScreenerOrdersResponse = DexScreenerOrderRaw[];

export interface DexScreenerPairPathParams {
  chainId: string;
  pairId: string;
}

export interface DexScreenerSearchPairsQuery {
  q: string;
}

export interface DexScreenerTokenPairsPathParams {
  chainId: string;
  tokenAddress: string;
}

export interface DexScreenerTokensByChainPathParams {
  chainId: string;
  tokenAddresses: string;
}

export interface DexScreenerTokenRefRaw {
  address?: string;
  name?: string;
  symbol?: string;
  [key: string]: unknown;
}

export interface DexScreenerTxnWindowRaw {
  buys?: number;
  sells?: number;
  [key: string]: unknown;
}

export type DexScreenerTxnsRaw = Record<
  string,
  DexScreenerTxnWindowRaw | undefined
>;

export type DexScreenerNumberBucketsRaw = Record<string, number | undefined>;

export interface DexScreenerLiquidityRaw {
  base?: number;
  quote?: number;
  usd?: number;
  [key: string]: unknown;
}

export interface DexScreenerWebsiteRaw {
  label?: string;
  url?: string;
  [key: string]: unknown;
}

export interface DexScreenerSocialRaw {
  handle?: string;
  platform?: string;
  [key: string]: unknown;
}

export interface DexScreenerPairInfoRaw {
  imageUrl?: string;
  socials?: DexScreenerSocialRaw[];
  websites?: DexScreenerWebsiteRaw[];
  [key: string]: unknown;
}

export interface DexScreenerBoostsRaw {
  active?: number;
  [key: string]: unknown;
}

export interface DexScreenerPairRaw {
  baseToken?: DexScreenerTokenRefRaw;
  boosts?: DexScreenerBoostsRaw;
  chainId?: string;
  dexId?: string;
  fdv?: number | null;
  info?: DexScreenerPairInfoRaw;
  labels?: string[] | null;
  liquidity?: DexScreenerLiquidityRaw | null;
  marketCap?: number | null;
  pairAddress?: string;
  pairCreatedAt?: number | null;
  priceChange?: DexScreenerNumberBucketsRaw | null;
  priceNative?: string;
  priceUsd?: string | null;
  quoteToken?: DexScreenerTokenRefRaw;
  txns?: DexScreenerTxnsRaw;
  url?: string;
  volume?: DexScreenerNumberBucketsRaw;
  [key: string]: unknown;
}

export interface DexScreenerPairsEnvelopeRaw {
  pairs?: DexScreenerPairRaw[] | null;
  schemaVersion?: string;
  [key: string]: unknown;
}

export type DexScreenerPairsByPairAddressResponse = DexScreenerPairsEnvelopeRaw;
export type DexScreenerSearchPairsResponse = DexScreenerPairsEnvelopeRaw;
export type DexScreenerTokenPairsResponse = DexScreenerPairRaw[];
export type DexScreenerTokensByChainResponse = DexScreenerPairRaw[];

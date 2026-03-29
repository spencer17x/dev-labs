export interface SignalToken {
  symbol?: string | null;
  name?: string | null;
  address?: string | null;
}

export interface SignalAuthor {
  id?: string | null;
  username?: string | null;
  display_name?: string | null;
}

export interface SignalEvent {
  id: string;
  source: string;
  subtype: string;
  timestamp: number;
  chain?: string | null;
  token: SignalToken;
  author?: SignalAuthor | null;
  text?: string | null;
  metrics?: Record<string, number>;
  raw?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface SignalContextToken {
  chain?: string | null;
  address?: string | null;
  symbol?: string | null;
  name?: string | null;
}

export interface SignalContextDexscreener {
  source?: string | null;
  paid?: boolean;
  timestamp?: number;
  url?: string | null;
  icon?: string | null;
  header?: string | null;
  description?: string | null;
  links?: Array<Record<string, unknown>>;
}

export interface SignalContextXXYY {
  market_cap?: number | null;
  holder_count?: number | null;
  follow_buy_count?: number | null;
  kol_buy_count?: number | null;
  follow_addresses?: string[];
  kol_names?: string[];
  project_twitter_url?: string | null;
  project_telegram_url?: string | null;
  [key: string]: unknown;
}

export interface SignalContextTwitter {
  profile_url?: string | null;
  username?: string | null;
  community_count?: number | null;
  followers_count?: number | null;
  friends_count?: number | null;
  statuses_count?: number | null;
}

export interface SignalContext {
  token?: SignalContextToken;
  dexscreener?: SignalContextDexscreener;
  xxyy?: SignalContextXXYY;
  twitter?: SignalContextTwitter;
  [key: string]: unknown;
}

export interface NotificationSummary {
  paid: boolean;
  marketCap: number | null;
  holderCount: number | null;
  communityCount: number | null;
  followersCount: number | null;
  twitterUsername: string | null;
  dexscreenerUrl: string | null;
  telegramUrl: string | null;
}

export interface NotificationRecord {
  id: string;
  notifiedAt: string;
  strategyId: string;
  channels: string[];
  message: string;
  event: SignalEvent;
  context: SignalContext;
  summary: NotificationSummary;
}

export interface DashboardFilters {
  search: string;
  watchTerms: string;
  chain: string;
  source: string;
  strategyId: string;
  minHolders: string;
  maxMarketCap: string;
  minCommunityCount: string;
  paidOnly: boolean;
}

export interface StrategySnapshot {
  id: string;
  enabled: boolean;
  source: string;
  chains: string[];
  channels: string[];
  minHolderCount: number | null;
  maxHolderCount: number | null;
  maxMarketCap: number | null;
  trackedKolNames: string[];
  trackedFollowAddresses: string[];
}

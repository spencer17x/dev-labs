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
  imageUrl?: string | null;
  header?: string | null;
  description?: string | null;
  priceUsd?: number | null;
  liquidityUsd?: number | null;
  marketCap?: number | null;
  fdv?: number | null;
  websites?: string[];
  socials?: Array<{
    handle?: string | null;
    platform?: string | null;
    url?: string | null;
  }>;
  links?: Array<Record<string, unknown>>;
}

export interface SignalContext {
  token?: SignalContextToken;
  dexscreener?: SignalContextDexscreener;
  [key: string]: unknown;
}

export interface NotificationSummary {
  paid: boolean;
  imageUrl: string | null;
  marketCap: number | null;
  holderCount: number | null;
  liquidityUsd: number | null;
  priceUsd: number | null;
  communityCount: number | null;
  dexscreenerUrl: string | null;
  telegramUrl: string | null;
}

export interface NotificationRecord {
  id: string;
  notifiedAt: string;
  channels: string[];
  message: string;
  event: SignalEvent;
  context: SignalContext;
  summary: NotificationSummary;
}

export type WatchTransport = 'auto' | 'ws' | 'http';
export type StrategyPreset =
  | 'none'
  | 'custom'
  | 'laohuang';
export type StrategyStatus =
  | 'all'
  | 'tracking'
  | 'drop'
  | 'rebound'
  | 'growth'
  | 'triggered';

export interface RuntimeRefreshResult {
  generatedAt: string;
  stored: number;
  notifications: NotificationRecord[];
  processed: number;
  subscriptions: string[];
}

export interface DashboardFilters {
  search: string;
  watchTerms: string;
  watchTransport: WatchTransport;
  watchSubscriptions: string[];
  strategyPreset: StrategyPreset;
  strategyStatus: StrategyStatus;
  strategySeedSubscription: string;
  strategySeedChain: string;
  strategyRequirePaid: boolean;
  strategyMaxFirstSeenFdv: string;
  strategyDropRatio: string;
  strategyReboundRatio: string;
  strategyReboundDelaySec: string;
  strategyGrowthPercent: string;
  strategyTrackHours: string;
  chains: string[];
  minMarketCap: string;
  maxMarketCap: string;
  minLiquidityUsd: string;
  maxLiquidityUsd: string;
  minFdv: string;
  maxFdv: string;
  requireTelegram: boolean;
  requireTwitter: boolean;
  requireWebsite: boolean;
  paidOnly: boolean;
}

export interface WatchRuntimeState {
  intervalSec: number;
  lastActivityAt: string | null;
  lastError: string | null;
  lastStartedAt: string | null;
  lastStatus: string;
  lastStatusDetail: string | null;
  limit: number | null;
  running: boolean;
  subscriptions: string[];
  transport: WatchTransport;
}

export interface RuntimeNetworkCheck {
  closeCode?: number | null;
  detail: string | null;
  durationMs: number;
  error: string | null;
  ok: boolean;
  status: 'ok' | 'error' | 'timeout';
  statusCode?: number | null;
  target: string;
}

export interface RuntimeDiagnosticsNotificationStore {
  count: number;
  isEmpty: boolean;
  mode: 'none';
  resetsOnRestart: boolean;
}

export interface RuntimeDiagnosticsResult {
  checkedAt: string;
  httpCheck: RuntimeNetworkCheck;
  notificationsStore: RuntimeDiagnosticsNotificationStore;
  proxyEnv: Record<string, string>;
  wsCheck: RuntimeNetworkCheck;
}

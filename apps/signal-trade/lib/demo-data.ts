import { ALL_DASHBOARD_CHAINS } from '@/lib/dashboard-chain-filters';
import { DEFAULT_DEX_WATCH_SUBSCRIPTIONS } from '@/lib/dexscreener-subscriptions';
import type { DashboardFilters } from '@/lib/types';

export const defaultDashboardFilters: DashboardFilters = {
  search: '',
  watchTerms: '',
  watchTransport: 'auto',
  watchSubscriptions: [...DEFAULT_DEX_WATCH_SUBSCRIPTIONS],
  strategyPreset: 'laohuang',
  strategyStatus: 'all',
  strategySeedSubscription: 'token_profiles_latest',
  strategySeedChain: 'solana',
  strategyRequirePaid: true,
  strategyMaxFirstSeenFdv: '80000',
  strategyDropRatio: '0.5',
  strategyReboundRatio: '1.2',
  strategyReboundDelaySec: '6',
  strategyGrowthPercent: '20',
  strategyTrackHours: '12',
  chains: [...ALL_DASHBOARD_CHAINS],
  minHolders: '',
  minMarketCap: '',
  maxHolders: '',
  maxMarketCap: '',
  minCommunityCount: '',
  paidOnly: false,
};

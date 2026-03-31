import { DEFAULT_DEX_WATCH_SUBSCRIPTIONS } from '@/lib/dexscreener-subscriptions';
import type { DashboardFilters } from '@/lib/types';

export const defaultDashboardFilters: DashboardFilters = {
  search: '',
  watchTerms: '',
  watchTransport: 'auto',
  watchSubscriptions: [...DEFAULT_DEX_WATCH_SUBSCRIPTIONS],
  chain: 'all',
  source: 'all',
  minHolders: '',
  maxHolders: '',
  maxMarketCap: '',
  minCommunityCount: '',
  kolNames: '',
  followAddresses: '',
  paidOnly: false,
};

import { normalizeDexWatchSubscriptions } from '@/lib/dexscreener-subscriptions';
import { defaultDashboardFilters } from '@/lib/demo-data';
import { normalizeStrategyPreset } from '@/lib/strategy-presets';
import type {
  DashboardFilters,
  StrategyPreset,
  StrategyStatus,
  WatchTransport,
} from '@/lib/types';

export function normalizeDashboardFilters(
  value: Partial<DashboardFilters> | Record<string, unknown> | null | undefined,
): DashboardFilters {
  return {
    search: readString(value, 'search'),
    watchTerms: readString(value, 'watchTerms'),
    watchTransport: readWatchTransport(value, 'watchTransport'),
    watchSubscriptions: readWatchSubscriptions(value),
    strategyPreset: readStrategyPreset(value, 'strategyPreset'),
    strategyStatus: readStrategyStatus(value, 'strategyStatus'),
    strategySeedSubscription:
      readString(value, 'strategySeedSubscription') || 'token_profiles_latest',
    strategySeedChain: readString(value, 'strategySeedChain') || 'solana',
    strategyRequirePaid: readBooleanWithFallback(value, 'strategyRequirePaid', true),
    strategyMaxFirstSeenFdv: sanitizeNumericInput(
      readString(value, 'strategyMaxFirstSeenFdv') || '80000',
    ),
    strategyDropRatio: sanitizeNumericInput(
      readString(value, 'strategyDropRatio') || '0.5',
    ),
    strategyReboundRatio: sanitizeNumericInput(
      readString(value, 'strategyReboundRatio') || '1.2',
    ),
    strategyReboundDelaySec: sanitizeNumericInput(
      readString(value, 'strategyReboundDelaySec') || '6',
    ),
    strategyGrowthPercent: sanitizeNumericInput(
      readString(value, 'strategyGrowthPercent') || '20',
    ),
    strategyTrackHours: sanitizeNumericInput(
      readString(value, 'strategyTrackHours') || '12',
    ),
    chain: readString(value, 'chain') || 'all',
    source: readString(value, 'source') || 'all',
    minHolders: sanitizeNumericInput(readString(value, 'minHolders')),
    maxHolders: sanitizeNumericInput(readString(value, 'maxHolders')),
    maxMarketCap: sanitizeNumericInput(readString(value, 'maxMarketCap')),
    minCommunityCount: sanitizeNumericInput(readString(value, 'minCommunityCount')),
    kolNames: readString(value, 'kolNames'),
    followAddresses: readString(value, 'followAddresses'),
    paidOnly: readBoolean(value, 'paidOnly'),
  };
}

export async function getDashboardFilters(): Promise<DashboardFilters> {
  return defaultDashboardFilters;
}

export async function saveDashboardFilters(
  filters: DashboardFilters,
): Promise<DashboardFilters> {
  return normalizeDashboardFilters(filters);
}

function sanitizeNumericInput(value: string | undefined): string {
  if (!value) {
    return '';
  }

  const trimmed = value.trim();
  if (!trimmed) {
    return '';
  }

  return /^-?\d+(\.\d+)?$/.test(trimmed) ? trimmed : '';
}

function readString(
  value: Partial<DashboardFilters> | Record<string, unknown> | null | undefined,
  key: keyof DashboardFilters,
): string {
  if (!value || typeof value !== 'object') {
    return '';
  }

  const raw = value[key];
  return typeof raw === 'string' ? raw.trim() : '';
}

function readBoolean(
  value: Partial<DashboardFilters> | Record<string, unknown> | null | undefined,
  key: keyof DashboardFilters,
): boolean {
  if (!value || typeof value !== 'object') {
    return false;
  }

  return Boolean(value[key]);
}

function readBooleanWithFallback(
  value: Partial<DashboardFilters> | Record<string, unknown> | null | undefined,
  key: keyof DashboardFilters,
  fallback: boolean,
): boolean {
  if (!value || typeof value !== 'object' || !Object.hasOwn(value, key)) {
    return fallback;
  }

  return Boolean(value[key]);
}

function readWatchTransport(
  value: Partial<DashboardFilters> | Record<string, unknown> | null | undefined,
  key: keyof DashboardFilters,
): WatchTransport {
  const raw = readString(value, key);
  return raw === 'ws' || raw === 'http' || raw === 'auto' ? raw : 'auto';
}

function readStrategyPreset(
  value: Partial<DashboardFilters> | Record<string, unknown> | null | undefined,
  key: keyof DashboardFilters,
): StrategyPreset {
  const raw = readString(value, key);
  return normalizeStrategyPreset(raw);
}

function readStrategyStatus(
  value: Partial<DashboardFilters> | Record<string, unknown> | null | undefined,
  key: keyof DashboardFilters,
): StrategyStatus {
  const raw = readString(value, key);
  return raw === 'tracking' ||
    raw === 'drop' ||
    raw === 'rebound' ||
    raw === 'growth' ||
    raw === 'triggered'
    ? raw
    : 'all';
}

function readWatchSubscriptions(
  value: Partial<DashboardFilters> | Record<string, unknown> | null | undefined,
): string[] {
  if (!value || typeof value !== 'object') {
    return normalizeDexWatchSubscriptions(undefined);
  }

  const rawValue = value as Record<string, unknown>;

  if (!Object.hasOwn(rawValue, 'watchSubscriptions')) {
    return normalizeDexWatchSubscriptions(undefined);
  }

  return normalizeDexWatchSubscriptions(rawValue.watchSubscriptions, {
    fallbackToDefault: false,
  });
}

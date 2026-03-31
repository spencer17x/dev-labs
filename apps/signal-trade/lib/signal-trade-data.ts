import { normalizeDexWatchSubscriptions } from '@/lib/dexscreener-subscriptions';
import { defaultDashboardFilters } from '@/lib/demo-data';
import type {
  DashboardFilters,
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

function readWatchTransport(
  value: Partial<DashboardFilters> | Record<string, unknown> | null | undefined,
  key: keyof DashboardFilters,
): WatchTransport {
  const raw = readString(value, key);
  return raw === 'ws' || raw === 'http' || raw === 'auto' ? raw : 'auto';
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

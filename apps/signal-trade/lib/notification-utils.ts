import { DEX_WATCH_SUBSCRIPTION_OPTIONS } from '@/lib/dexscreener-subscriptions';
import type { NotificationRecord } from '@/lib/types';

const MAX_SESSION_NOTIFICATIONS = 250;

export function mergeNotifications(
  current: NotificationRecord[],
  incoming: NotificationRecord[],
): NotificationRecord[] {
  const merged = new Map<string, NotificationRecord>();

  for (const record of [...incoming, ...current]) {
    const existing = merged.get(record.id);
    if (!existing) {
      merged.set(record.id, record);
      continue;
    }

    if (
      new Date(record.notifiedAt).getTime() >
      new Date(existing.notifiedAt).getTime()
    ) {
      merged.set(record.id, record);
    }
  }

  return Array.from(merged.values())
    .sort(
      (left, right) =>
        new Date(right.notifiedAt).getTime() - new Date(left.notifiedAt).getTime(),
    )
    .slice(0, MAX_SESSION_NOTIFICATIONS);
}

export function parseListFilter(value: string): string[] {
  return value
    .split(/[\n,]/)
    .map(item => item.trim().toLowerCase())
    .filter(Boolean);
}

export function uniqueValues(values: string[]): string[] {
  return Array.from(
    new Set(values.map(item => item.trim()).filter(Boolean)),
  ).sort((left, right) => left.localeCompare(right));
}

export function getSelectedWatchSubscriptions(value: string[]): string[] {
  return DEX_WATCH_SUBSCRIPTION_OPTIONS
    .map(option => option.id)
    .filter(option => value.includes(option));
}

export function toggleWatchSubscription(
  selectedSubscriptions: string[],
  subscription: string,
): string[] {
  const nextSelected = selectedSubscriptions.includes(subscription)
    ? selectedSubscriptions.filter(item => item !== subscription)
    : [...selectedSubscriptions, subscription];

  return DEX_WATCH_SUBSCRIPTION_OPTIONS
    .map(option => option.id)
    .filter(option => nextSelected.includes(option));
}

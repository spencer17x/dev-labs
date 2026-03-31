export const DEFAULT_DEX_WATCH_SUBSCRIPTIONS = ['token_profiles_latest'] as const;

export const DEX_WATCH_SUBSCRIPTION_OPTIONS = [
  {
    id: 'token_profiles_latest',
    label: 'token profiles',
  },
  {
    id: 'community_takeovers_latest',
    label: 'community takeovers',
  },
  {
    id: 'ads_latest',
    label: 'ads',
  },
  {
    id: 'token_boosts_latest',
    label: 'boosted tokens',
  },
  {
    id: 'token_boosts_top',
    label: 'most active boosts',
  },
] as const;

const DEX_WATCH_SUBSCRIPTION_IDS = new Set<string>(
  DEX_WATCH_SUBSCRIPTION_OPTIONS.map(option => option.id),
);

type NormalizeDexWatchSubscriptionsOptions = {
  fallbackToDefault?: boolean;
};

export function getDexWatchSubscriptionLabel(subscription: string): string {
  return (
    DEX_WATCH_SUBSCRIPTION_OPTIONS.find(option => option.id === subscription)?.label ??
    subscription
  );
}

export function normalizeDexWatchSubscriptions(
  value: unknown,
  options: NormalizeDexWatchSubscriptionsOptions = {},
): string[] {
  const fallbackToDefault = options.fallbackToDefault ?? true;

  if (!Array.isArray(value)) {
    return fallbackToDefault ? [...DEFAULT_DEX_WATCH_SUBSCRIPTIONS] : [];
  }

  const normalized = Array.from(
    new Set(
      value.filter(
        (item): item is string =>
          typeof item === 'string' && DEX_WATCH_SUBSCRIPTION_IDS.has(item),
      ),
    ),
  );

  if (normalized.length > 0) {
    return normalized;
  }

  return fallbackToDefault ? [...DEFAULT_DEX_WATCH_SUBSCRIPTIONS] : [];
}

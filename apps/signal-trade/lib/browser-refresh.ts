import type { NotificationRecord } from './types.ts';

type BrowserRefreshFetch = (
  input: string | URL,
  init?: RequestInit,
) => Promise<{
  json(): Promise<unknown>;
  ok: boolean;
  status: number;
  text(): Promise<string>;
}>;

type BrowserRefreshResult = {
  notifications: NotificationRecord[];
  processed: number;
  stored: number;
  subscriptions: string[];
};

type RuntimeIngestResult = {
  message?: string;
  notifications?: NotificationRecord[];
  processed?: number;
  stored?: number;
};

type RefreshDexNotificationsInBrowserOptions = {
  fetcher?: BrowserRefreshFetch;
  limit: number;
  subscriptions: string[];
};

export async function refreshDexNotificationsInBrowser(
  options: RefreshDexNotificationsInBrowserOptions,
): Promise<BrowserRefreshResult> {
  const fetcher = options.fetcher ?? fetch;
  const notifications: NotificationRecord[] = [];
  let processed = 0;
  let stored = 0;

  for (const subscription of options.subscriptions) {
    const latestResponse = await fetcher(
      buildDexSubscriptionHttpUrl(subscription, options.limit),
      {
        cache: 'no-store',
        headers: {
          Accept: 'application/json',
        },
      },
    );
    const payloadText = await latestResponse.text();

    if (!latestResponse.ok) {
      throw new Error(`dexscreener request failed: ${latestResponse.status}`);
    }

    const ingestResponse = await fetcher('/api/runtime/ingest', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        limit: options.limit,
        payloadText,
        subscription,
      }),
    });
    const ingestPayload = (await ingestResponse.json().catch(() => ({}))) as RuntimeIngestResult;

    if (!ingestResponse.ok) {
      throw new Error(
        typeof ingestPayload.message === 'string' && ingestPayload.message.trim()
          ? ingestPayload.message.trim()
          : `unexpected status ${ingestResponse.status}`,
      );
    }

    if (Array.isArray(ingestPayload.notifications)) {
      notifications.push(...ingestPayload.notifications);
    }
    processed += ingestPayload.processed ?? 0;
    stored += ingestPayload.stored ?? 0;
  }

  return {
    notifications,
    processed,
    stored,
    subscriptions: [...options.subscriptions],
  };
}

export function buildDexSubscriptionHttpUrl(
  subscription: string,
  limit: number,
): string {
  const endpoint =
    subscription === 'community_takeovers_latest'
      ? '/community-takeovers/latest/v1'
      : subscription === 'ads_latest'
        ? '/ads/latest/v1'
        : subscription === 'token_boosts_latest'
          ? '/token-boosts/latest/v1'
          : subscription === 'token_boosts_top'
            ? '/token-boosts/top/v1'
            : '/token-profiles/latest/v1';

  const url = new URL(endpoint, 'https://api.dexscreener.com');
  if (limit > 0) {
    url.searchParams.set('limit', String(limit));
  }
  return url.toString();
}

import type { SignalContextTwitter } from '@/lib/types';
import { signalTradeConfig } from '@/lib/runtime/config';

const X_GRAPHQL_BASE_URL = 'https://api.x.com/graphql';
const USER_BY_SCREEN_NAME_QUERY_ID = 'pLsOiyHJ1eFwPJlNmLp4Bg';

const USER_BY_SCREEN_NAME_FEATURES = {
  hidden_profile_subscriptions_enabled: true,
  profile_label_improvements_pcf_label_in_post_enabled: true,
  responsive_web_profile_redirect_enabled: false,
  rweb_tipjar_consumption_enabled: false,
  verified_phone_label_enabled: false,
  subscriptions_verification_info_is_identity_verified_enabled: true,
  subscriptions_verification_info_verified_since_enabled: true,
  highlights_tweets_tab_ui_enabled: true,
  responsive_web_twitter_article_notes_tab_enabled: true,
  subscriptions_feature_can_gift_premium: true,
  creator_subscriptions_tweet_preview_api_enabled: true,
  responsive_web_graphql_skip_user_profile_image_extensions_enabled: false,
  responsive_web_graphql_timeline_navigation_enabled: true,
} satisfies Record<string, boolean>;

const USER_BY_SCREEN_NAME_FIELD_TOGGLES = {
  withPayments: false,
  withAuxiliaryUserLabels: true,
} satisfies Record<string, boolean>;

export async function fetchTwitterProfileMetrics(
  username: string,
): Promise<SignalContextTwitter> {
  const normalized = username.trim().replace(/^@/, '').toLowerCase();
  if (!normalized) {
    return emptyTwitterMetrics(null);
  }

  if (!signalTradeConfig.twitterAuth.ct0 || !signalTradeConfig.twitterAuth.authToken) {
    return emptyTwitterMetrics(normalized);
  }

  const url = new URL(
    `${X_GRAPHQL_BASE_URL}/${USER_BY_SCREEN_NAME_QUERY_ID}/UserByScreenName`,
  );
  url.searchParams.set(
    'variables',
    JSON.stringify({
      screen_name: normalized,
      withGrokTranslatedBio: false,
    }),
  );
  url.searchParams.set('features', JSON.stringify(USER_BY_SCREEN_NAME_FEATURES));
  url.searchParams.set(
    'fieldToggles',
    JSON.stringify(USER_BY_SCREEN_NAME_FIELD_TOGGLES),
  );

  try {
    const response = await fetch(url, {
      headers: {
        authorization: signalTradeConfig.twitterAuth.bearerToken,
        cookie: `ct0=${signalTradeConfig.twitterAuth.ct0}; auth_token=${signalTradeConfig.twitterAuth.authToken}`,
        referer: 'https://x.com/',
        'user-agent':
          'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'x-csrf-token': signalTradeConfig.twitterAuth.ct0,
        'x-twitter-active-user': 'yes',
        'x-twitter-client-language': 'en',
      },
      next: { revalidate: 0 },
      signal: AbortSignal.timeout(signalTradeConfig.twitter.requestTimeoutSec * 1000),
    });

    if (!response.ok) {
      return emptyTwitterMetrics(normalized);
    }

    const payload = (await response.json()) as unknown;
    const result = extractFirstUserResult(payload);
    const legacy = isObject(result?.legacy) ? result.legacy : {};

    return {
      username: normalized,
      community_count: asInteger(legacy.followers_count),
      followers_count: asInteger(legacy.followers_count),
      friends_count: asInteger(legacy.friends_count),
      statuses_count: asInteger(legacy.statuses_count),
      profile_url: `https://x.com/${normalized}`,
    };
  } catch {
    return emptyTwitterMetrics(normalized);
  }
}

export function extractTwitterUsername(profileUrl: unknown): string | null {
  if (typeof profileUrl !== 'string' || !profileUrl.trim()) {
    return null;
  }

  try {
    const parsed = new URL(profileUrl);
    const parts = parsed.pathname.split('/').filter(Boolean);
    if (parts.length === 0) {
      return null;
    }
    if (parts[0] === 'i' && parts[1] === 'communities') {
      return null;
    }
    return parts[0]?.replace(/^@/, '') ?? null;
  } catch {
    return null;
  }
}

export function findSocialLink(
  links: unknown,
  types: string[],
): string | null {
  if (!Array.isArray(links)) {
    return null;
  }

  const normalizedTypes = new Set(types.map(item => item.toLowerCase()));
  for (const link of links) {
    if (!isObject(link)) {
      continue;
    }
    const linkType = typeof link.type === 'string' ? link.type.toLowerCase() : '';
    if (!normalizedTypes.has(linkType)) {
      continue;
    }
    if (typeof link.url === 'string' && link.url.trim()) {
      return link.url.trim();
    }
  }

  return null;
}

function extractFirstUserResult(payload: unknown): Record<string, unknown> | null {
  for (const node of walk(payload)) {
    if (!isObject(node)) {
      continue;
    }
    const legacy = node.legacy;
    const restId = node.rest_id;
    if (!isObject(legacy) || typeof restId !== 'string') {
      continue;
    }
    const screenName =
      typeof legacy.screen_name === 'string' ? legacy.screen_name : null;
    if (screenName) {
      return node;
    }
  }
  return null;
}

function* walk(value: unknown): Generator<unknown> {
  if (Array.isArray(value)) {
    for (const item of value) {
      yield* walk(item);
    }
    return;
  }

  if (isObject(value)) {
    yield value;
    for (const item of Object.values(value)) {
      yield* walk(item);
    }
  }
}

function emptyTwitterMetrics(username: string | null): SignalContextTwitter {
  return {
    username,
    profile_url: username ? `https://x.com/${username}` : null,
    community_count: null,
    followers_count: null,
    friends_count: null,
    statuses_count: null,
  };
}

function asInteger(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Math.trunc(value);
  }
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? Math.trunc(parsed) : null;
  }
  return null;
}

function isObject(value: unknown): value is Record<string, any> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

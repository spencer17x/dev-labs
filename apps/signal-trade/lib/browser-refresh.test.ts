import assert from 'node:assert/strict';
import test from 'node:test';

import { refreshDexNotificationsInBrowser } from './browser-refresh.ts';

test('fetches Dex latest payloads in browser and ingests them into notifications', async () => {
  const fetchCalls: Array<{ input: string; init?: RequestInit }> = [];

  const result = await refreshDexNotificationsInBrowser({
    fetcher: async (input, init) => {
      const url = String(input);
      fetchCalls.push({ input: url, init });

      if (url === 'https://api.dexscreener.com/token-profiles/latest/v1?limit=10') {
        return createTextResponse(
          200,
          '[{"chainId":"solana","tokenAddress":"So11111111111111111111111111111111111111112"}]',
        );
      }

      if (url === 'https://api.dexscreener.com/token-boosts/latest/v1?limit=10') {
        return createTextResponse(
          200,
          '[{"chainId":"solana","tokenAddress":"Bo11111111111111111111111111111111111111112","amount":1}]',
        );
      }

      if (url === '/api/runtime/ingest') {
        const body = JSON.parse(String(init?.body ?? '{}')) as {
          payloadText?: string;
          subscription?: string;
        };

        if (body.subscription === 'token_profiles_latest') {
          assert.match(
            body.payloadText ?? '',
            /So11111111111111111111111111111111111111112/,
          );
          return createJsonResponse(200, {
            notifications: [buildNotification('profile-1')],
            processed: 1,
            stored: 1,
          });
        }

        if (body.subscription === 'token_boosts_latest') {
          assert.match(
            body.payloadText ?? '',
            /Bo11111111111111111111111111111111111111112/,
          );
          return createJsonResponse(200, {
            notifications: [buildNotification('boost-1')],
            processed: 2,
            stored: 1,
          });
        }
      }

      throw new Error(`unexpected fetch ${url}`);
    },
    limit: 10,
    subscriptions: ['token_profiles_latest', 'token_boosts_latest'],
  });

  assert.equal(result.processed, 3);
  assert.equal(result.stored, 2);
  assert.deepEqual(
    result.notifications.map(record => record.id),
    ['profile-1', 'boost-1'],
  );
  assert.deepEqual(fetchCalls.map(call => call.input), [
    'https://api.dexscreener.com/token-profiles/latest/v1?limit=10',
    '/api/runtime/ingest',
    'https://api.dexscreener.com/token-boosts/latest/v1?limit=10',
    '/api/runtime/ingest',
  ]);
});

test('surfaces Dex latest request failures', async () => {
  await assert.rejects(
    () =>
      refreshDexNotificationsInBrowser({
        fetcher: async () => createTextResponse(503, 'unavailable'),
        limit: 10,
        subscriptions: ['token_profiles_latest'],
      }),
    /dexscreener request failed: 503/,
  );
});

function buildNotification(id: string) {
  return {
    id,
    notifiedAt: '2026-04-04T00:00:00.000Z',
    channels: [],
    message: id,
    event: {
      id,
      source: 'dexscreener',
      subtype: 'token_profiles_latest',
      timestamp: 1,
      token: {
        address: 'So11111111111111111111111111111111111111112',
      },
    },
    context: {},
    summary: {
      paid: false,
      imageUrl: null,
      marketCap: null,
      holderCount: null,
      liquidityUsd: null,
      priceUsd: null,
      communityCount: null,
      dexscreenerUrl: null,
      telegramUrl: null,
    },
  };
}

function createTextResponse(status: number, body: string) {
  return {
    ok: status >= 200 && status < 300,
    status,
    async json() {
      return JSON.parse(body);
    },
    async text() {
      return body;
    },
  };
}

function createJsonResponse(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    async json() {
      return body;
    },
    async text() {
      return JSON.stringify(body);
    },
  };
}

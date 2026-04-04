import assert from 'node:assert/strict';
import test from 'node:test';

import {
  splitDisplayReadyNotifications,
  streamBackfilledNotifications,
  type FetchNotificationDetailsByChain,
} from './browser-notification-details.ts';

test('holds notifications missing token identity until detail backfill is ready', () => {
  const readyNotification = buildNotification(1, {
    detailState: 'complete',
  });
  const pendingNotification = buildNotification(2, {
    detailState: 'missing_identity',
  });

  const { deferredNotifications, immediateNotifications } =
    splitDisplayReadyNotifications([readyNotification, pendingNotification]);

  assert.deepEqual(
    immediateNotifications.map(record => record.id),
    ['token-1'],
  );
  assert.deepEqual(
    deferredNotifications.map(record => record.id),
    ['token-2'],
  );
});

test('streams notification detail backfill in address batches instead of swallowing the whole set', async () => {
  const notifications = Array.from({ length: 65 }, (_, index) =>
    buildNotification(index + 1),
  );
  const requestedBatches: string[][] = [];
  const deliveredBatchSizes: number[] = [];

  const fetchDetailsByChain: FetchNotificationDetailsByChain = async (
    chain,
    tokenAddresses,
  ) => {
    assert.equal(chain, 'solana');
    requestedBatches.push([...tokenAddresses]);

    return Object.fromEntries(
      tokenAddresses.map(address => [
        address.toLowerCase(),
        {
          fdv: 1_000,
          marketCap: 900,
          priceUsd: 0.001,
          token: {
            name: `Token ${address.slice(-2)}`,
            symbol: `T${address.slice(-2)}`,
          },
        },
      ]),
    );
  };

  await streamBackfilledNotifications(notifications, {
    fetchDetailsByChain,
    onBatch: batch => {
      deliveredBatchSizes.push(batch.length);
    },
  });

  assert.deepEqual(
    requestedBatches.map(batch => batch.length),
    [30, 30, 5],
  );
  assert.deepEqual(deliveredBatchSizes, [30, 30, 5]);
});

function buildNotification(
  index: number,
  options: {
    detailState?: 'complete' | 'missing_identity';
  } = {},
) {
  const address = `So${String(index).padStart(40, '0')}`;
  const detailState = options.detailState ?? 'missing_identity';

  return {
    id: `token-${index}`,
    notifiedAt: '2026-04-04T00:00:00.000Z',
    channels: [],
    message: `token-${index}`,
    event: {
      id: `token-${index}`,
      source: 'dexscreener',
      subtype: 'token_profiles_latest',
      timestamp: 1,
      chain: 'solana',
      token: {
        address,
      },
    },
    context: {
      token: {
        address,
        chain: 'solana',
        name: detailState === 'complete' ? `Token ${index}` : null,
        symbol: detailState === 'complete' ? `T${index}` : null,
      },
      dexscreener:
        detailState === 'complete'
          ? {
              fdv: 1_000,
              liquidityUsd: 500,
              marketCap: 900,
              priceUsd: 0.001,
            }
          : {},
    },
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

import assert from 'node:assert/strict';
import test from 'node:test';

import {
  streamBackfilledNotifications,
  type FetchNotificationDetailsByChain,
} from './browser-notification-details.ts';

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

function buildNotification(index: number) {
  const address = `So${String(index).padStart(40, '0')}`;

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
      },
      dexscreener: {},
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

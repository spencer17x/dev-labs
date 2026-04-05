import assert from 'node:assert/strict';
import test from 'node:test';

import { parseDexSubscriptionPayload } from './ingest-dex-payload.ts';

test('parses token profile payload shaped like the REST docs sample', () => {
  const events = parseDexSubscriptionPayload('token_profiles_latest', {
    url: 'https://dexscreener.com/solana/token',
    chainId: 'solana',
    tokenAddress: 'So11111111111111111111111111111111111111112',
    icon: 'https://cdn.example/icon.png',
    header: 'https://cdn.example/header.png',
    description: 'profile from docs',
    links: [
      {
        type: 'website',
        label: 'Website',
        url: 'https://example.com',
      },
    ],
  });

  assert.equal(events.length, 1);
  assert.deepEqual(events[0], {
    id: 'token_profiles_latest:solana:So11111111111111111111111111111111111111112:::',
    source: 'dexscreener',
    subtype: 'token_profiles_latest',
    timestamp: events[0]!.timestamp,
    chain: 'solana',
    token: {
      symbol: null,
      name: null,
      address: 'So11111111111111111111111111111111111111112',
    },
    author: null,
    text: 'profile from docs',
    metrics: {},
    raw: {
      url: 'https://dexscreener.com/solana/token',
      chainId: 'solana',
      tokenAddress: 'So11111111111111111111111111111111111111112',
      icon: 'https://cdn.example/icon.png',
      header: 'https://cdn.example/header.png',
      description: 'profile from docs',
      links: [
        {
          type: 'website',
          label: 'Website',
          url: 'https://example.com',
        },
      ],
    },
    metadata: {
      subscription: 'token_profiles_latest',
      dexscreener: {
        url: 'https://dexscreener.com/solana/token',
        icon: 'https://cdn.example/icon.png',
        header: 'https://cdn.example/header.png',
        description: 'profile from docs',
        links: [
          {
            type: 'website',
            label: 'Website',
            url: 'https://example.com',
          },
        ],
      },
    },
  });
});

test('parses websocket envelope shaped like the websocket docs sample', () => {
  const events = parseDexSubscriptionPayload(
    'token_boosts_latest',
    {
      limit: 90,
      data: [
        {
          url: 'https://dexscreener.com/solana/token',
          chainId: 'solana',
          tokenAddress: 'So11111111111111111111111111111111111111112',
          amount: 1,
          totalAmount: 3,
          icon: 'https://cdn.example/icon.png',
          header: 'https://cdn.example/header.png',
          description: 'boost from docs',
          links: [
            {
              type: 'twitter',
              label: 'X',
              url: 'https://x.com/example',
            },
          ],
        },
      ],
    },
    10,
  );

  assert.equal(events.length, 1);
  assert.equal(events[0]?.subtype, 'token_boosts_latest');
  assert.equal(events[0]?.chain, 'solana');
  assert.equal(
    events[0]?.token.address,
    'So11111111111111111111111111111111111111112',
  );
  assert.deepEqual(events[0]?.metrics, {
    amount: 1,
    totalAmount: 3,
  });
  assert.equal(events[0]?.text, 'boost from docs');
});

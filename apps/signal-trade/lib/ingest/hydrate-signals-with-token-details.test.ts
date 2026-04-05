import assert from 'node:assert/strict';
import test from 'node:test';

import { hydrateStoredSignalsWithTokenDetails } from './hydrate-signals-with-token-details.ts';

test('falls back to original signals when token detail hydration exceeds deadline', async () => {
  const signals = [
    {
      event: {
        chain: 'solana',
        token: {
          address: 'So11111111111111111111111111111111111111112',
        },
      },
      context: {
        token: {
          chain: 'solana',
          address: 'So11111111111111111111111111111111111111112',
        },
      },
    },
  ];

  const startedAt = Date.now();
  const result = await hydrateStoredSignalsWithTokenDetails(signals, {
    buildTokenKey,
    fetchDetailsByChain: async () => {
      return await new Promise<Record<string, { name: string } | null>>(() => {});
    },
    maxWaitMs: 20,
    mergeSignalWithDetail: (signal, detail) => ({
      ...signal,
      context: {
        ...signal.context,
        detail,
      },
    }),
  });

  assert.equal(result, signals);
  assert.ok(Date.now() - startedAt < 200);
});

test('merges detail into signals when token detail hydration completes in time', async () => {
  const signals = [
    {
      event: {
        chain: 'solana',
        token: {
          address: 'So11111111111111111111111111111111111111112',
        },
      },
      context: {
        token: {
          chain: 'solana',
          address: 'So11111111111111111111111111111111111111112',
        },
      },
    },
  ];

  const result = await hydrateStoredSignalsWithTokenDetails(signals, {
    buildTokenKey,
    fetchDetailsByChain: async () => ({
      so11111111111111111111111111111111111111112: {
        name: 'Wrapped SOL',
      },
    }),
    maxWaitMs: 200,
    mergeSignalWithDetail: (signal, detail) => ({
      ...signal,
      context: {
        ...signal.context,
        detail,
      },
    }),
  });

  assert.notEqual(result, signals);
  assert.deepEqual(result, [
    {
      event: {
        chain: 'solana',
        token: {
          address: 'So11111111111111111111111111111111111111112',
        },
      },
      context: {
        token: {
          chain: 'solana',
          address: 'So11111111111111111111111111111111111111112',
        },
        detail: {
          name: 'Wrapped SOL',
        },
      },
    },
  ]);
});

function buildTokenKey(
  chainId: string | null | undefined,
  tokenAddress: string | null | undefined,
): string | null {
  if (!chainId || !tokenAddress) {
    return null;
  }

  return `${chainId.toLowerCase()}:${tokenAddress.toLowerCase()}`;
}

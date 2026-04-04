import assert from 'node:assert/strict';
import test from 'node:test';

import { parseRuntimeIngestInput } from './runtime-ingest.ts';

test('keeps all websocket items when runtime ingest request omits limit', () => {
  const payload = {
    data: Array.from({ length: 90 }, (_, index) => ({
      chainId: 'solana',
      description: `item-${index + 1}`,
      tokenAddress: `So${String(index + 1).padStart(40, '0')}`,
      url: `https://dexscreener.com/solana/token-${index + 1}`,
    })),
    limit: 90,
  };

  const result = parseRuntimeIngestInput({
    payload,
    subscription: 'token_profiles_latest',
  });

  assert.equal(result.events.length, 90);
  assert.equal(result.subscription, 'token_profiles_latest');
});

test('applies explicit runtime ingest limit when provided', () => {
  const payload = {
    data: Array.from({ length: 90 }, (_, index) => ({
      chainId: 'solana',
      description: `item-${index + 1}`,
      tokenAddress: `So${String(index + 1).padStart(40, '0')}`,
      url: `https://dexscreener.com/solana/token-${index + 1}`,
    })),
    limit: 90,
  };

  const result = parseRuntimeIngestInput({
    limit: 10,
    payload,
    subscription: 'token_profiles_latest',
  });

  assert.equal(result.events.length, 10);
});

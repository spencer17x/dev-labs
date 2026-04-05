import assert from 'node:assert/strict';
import test from 'node:test';

test('ingests a latest payload into notifications without a runtime route hop', async () => {
  const { ingestDexPayload } = await import('./ingest-dex-payload.ts');

  const result = await ingestDexPayload({
    fetchDetailsByChain: async () => ({}),
    payload: [
      {
        chainId: 'solana',
        description: 'profile payload',
        tokenAddress: 'So11111111111111111111111111111111111111112',
        url: 'https://dexscreener.com/solana/token',
      },
    ],
    subscription: 'token_profiles_latest',
  });

  assert.equal(result.subscription, 'token_profiles_latest');
  assert.equal(result.processed, 1);
  assert.equal(result.stored, 1);
  assert.equal(result.notifications.length, 1);
  assert.equal(
    result.notifications[0]?.event.token.address,
    'So11111111111111111111111111111111111111112',
  );
  assert.equal(result.notifications[0]?.summary.paid, true);
});

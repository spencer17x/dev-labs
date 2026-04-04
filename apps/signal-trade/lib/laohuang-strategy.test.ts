import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildLaohuangState,
  type LaohuangStrategyConfig,
} from './laohuang-strategy.ts';

test('laohuang strategy only tracks real fdv values', () => {
  const config: LaohuangStrategyConfig = {
    chain: 'solana',
    dropRatio: 0.5,
    growthPercent: 20,
    maxFirstSeenFdv: 80_000,
    reboundDelayMs: 6_000,
    reboundRatio: 1.2,
    requirePaid: false,
    seedSourceKey: 'dexscreener.token_profiles_latest',
    trackWindowMs: 60_000,
  };

  const records = [
    {
      notifiedAt: '2026-04-04T10:00:00.000Z',
      event: {
        chain: 'solana',
        source: 'dexscreener',
        subtype: 'token_profiles_latest',
        token: {
          address: '9gLshEn5yRPf7vQPjXF558RiVu5hR2Eg8yPNa67ipump',
        },
      },
      context: {
        token: {
          address: '9gLshEn5yRPf7vQPjXF558RiVu5hR2Eg8yPNa67ipump',
        },
        dexscreener: {
          fdv: 25_000,
          marketCap: 25_000,
          priceUsd: 0.000025,
        },
      },
      summary: {
        marketCap: 25_000,
        paid: true,
        priceUsd: 0.000025,
      },
    },
    {
      notifiedAt: '2026-04-04T10:01:00.000Z',
      event: {
        chain: 'solana',
        source: 'dexscreener',
        subtype: 'token_boosts_latest',
        token: {
          address: '9gLshEn5yRPf7vQPjXF558RiVu5hR2Eg8yPNa67ipump',
        },
      },
      context: {
        token: {
          address: '9gLshEn5yRPf7vQPjXF558RiVu5hR2Eg8yPNa67ipump',
        },
        dexscreener: {
          fdv: null,
          marketCap: 110_000,
          priceUsd: 0.00011,
        },
      },
      summary: {
        marketCap: 110_000,
        paid: true,
        priceUsd: 0.00011,
      },
    },
  ];

  const states = buildLaohuangState(records, config);
  const state = states['solana:9glshen5yrpf7vqpjxf558rivu5hr2eg8ypna67ipump'];

  assert.ok(state);
  assert.equal(state.firstSeenFdv, 25_000);
  assert.equal(state.currentFdv, 25_000);
  assert.equal(state.growthTriggered, false);
});

import assert from 'node:assert/strict';
import test from 'node:test';

import { matchesMarketCapRange } from './dashboard-market-cap.ts';

test('matchesMarketCapRange returns true when no bounds are set', () => {
  assert.equal(matchesMarketCapRange(null, { min: null, max: null }), true);
  assert.equal(matchesMarketCapRange(1_000, { min: null, max: null }), true);
});

test('matchesMarketCapRange applies minimum and maximum bounds inclusively', () => {
  assert.equal(matchesMarketCapRange(1_000, { min: 1_000, max: 2_000 }), true);
  assert.equal(matchesMarketCapRange(900, { min: 1_000, max: 2_000 }), false);
  assert.equal(matchesMarketCapRange(2_100, { min: 1_000, max: 2_000 }), false);
});

test('matchesMarketCapRange excludes missing market cap when a bound is required', () => {
  assert.equal(matchesMarketCapRange(null, { min: 1_000, max: null }), false);
  assert.equal(matchesMarketCapRange(null, { min: null, max: 2_000 }), false);
});

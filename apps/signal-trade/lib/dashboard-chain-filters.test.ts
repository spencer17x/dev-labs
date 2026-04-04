import assert from 'node:assert/strict';
import test from 'node:test';

import {
  ALL_DASHBOARD_CHAINS,
  areAllDashboardChainsSelected,
  matchesDashboardChainSelection,
  normalizeDashboardChains,
} from './dashboard-chain-filters.ts';

test('normalizeDashboardChains falls back to all supported chains', () => {
  assert.deepEqual(normalizeDashboardChains(undefined), ALL_DASHBOARD_CHAINS);
  assert.deepEqual(normalizeDashboardChains([]), ALL_DASHBOARD_CHAINS);
  assert.deepEqual(normalizeDashboardChains(['base', 'unknown', 'solana']), [
    'base',
    'solana',
  ]);
});

test('all selected chains means no chain filtering', () => {
  assert.equal(areAllDashboardChainsSelected(ALL_DASHBOARD_CHAINS), true);
  assert.equal(matchesDashboardChainSelection('solana', ALL_DASHBOARD_CHAINS), true);
  assert.equal(matchesDashboardChainSelection('ethereum', ALL_DASHBOARD_CHAINS), true);
  assert.equal(matchesDashboardChainSelection(null, ALL_DASHBOARD_CHAINS), true);
});

test('partial chain selection filters out unsupported results', () => {
  const selectedChains = normalizeDashboardChains(['solana', 'bsc']);

  assert.equal(matchesDashboardChainSelection('solana', selectedChains), true);
  assert.equal(matchesDashboardChainSelection('bsc', selectedChains), true);
  assert.equal(matchesDashboardChainSelection('base', selectedChains), false);
  assert.equal(matchesDashboardChainSelection(null, selectedChains), false);
});

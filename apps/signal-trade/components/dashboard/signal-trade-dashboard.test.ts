import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const DASHBOARD_PATH = path.resolve(import.meta.dirname, 'signal-trade-dashboard.tsx');

test('dashboard source exposes pagination controls for scan results', () => {
  const source = readFileSync(DASHBOARD_PATH, 'utf8');

  assert.match(source, /每页/);
  assert.match(source, /自定义/);
  assert.match(source, /首页/);
  assert.match(source, /尾页/);
  assert.match(source, /paginatedNotifications/);
  assert.match(source, /matchesDashboardChainSelection/);
  assert.match(source, /filters\.minMarketCap/);
  assert.match(source, /filters\.chains/);
  assert.doesNotMatch(source, /filters\.source/);
});

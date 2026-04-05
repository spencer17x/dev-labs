import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const DASHBOARD_PATH = path.resolve(import.meta.dirname, 'signal-trade-dashboard.tsx');
const FILTER_DIALOG_PATH = path.resolve(import.meta.dirname, 'filter-dialog.tsx');

test('dashboard source exposes pagination controls for scan results', () => {
  const source = readFileSync(DASHBOARD_PATH, 'utf8');

  assert.match(source, /每页/);
  assert.match(source, /自定义/);
  assert.match(source, /首页/);
  assert.match(source, /尾页/);
  assert.match(source, /paginatedNotifications/);
  assert.match(source, /matchesDashboardChainSelection/);
  assert.match(source, /filters\.minLiquidityUsd/);
  assert.match(source, /filters\.maxLiquidityUsd/);
  assert.match(source, /filters\.minFdv/);
  assert.match(source, /filters\.maxFdv/);
  assert.match(source, /filters\.requireTelegram/);
  assert.match(source, /filters\.requireTwitter/);
  assert.match(source, /filters\.requireWebsite/);
  assert.match(source, /filters\.minMarketCap/);
  assert.match(source, /filters\.maxMarketCap/);
  assert.match(source, /filters\.paidOnly/);
  assert.match(source, /filters\.chains/);
  assert.doesNotMatch(source, /filters\.minHolders/);
  assert.doesNotMatch(source, /filters\.maxHolders/);
  assert.doesNotMatch(source, /holderCount/);
  assert.doesNotMatch(source, /minCommunityCount/);
  assert.doesNotMatch(source, /filters\.source\b/);
  assert.doesNotMatch(source, /filters\.sourceSubscriptions/);
});

test('dashboard source updates relative time on a short client interval', () => {
  const source = readFileSync(DASHBOARD_PATH, 'utf8');

  assert.match(source, /RELATIVE_TIME_TICK_MS/);
  assert.doesNotMatch(source, /60_000/);
});

test('filter dialog exposes supported Dex-backed filters with prompt placeholders', () => {
  const source = readFileSync(FILTER_DIALOG_PATH, 'utf8');

  assert.match(source, /FieldGroup label="链"/);
  assert.match(source, /FieldGroup label="最低市值"/);
  assert.match(source, /FieldGroup label="最高市值"/);
  assert.match(source, /FieldGroup label="最低流动性"/);
  assert.match(source, /FieldGroup label="最高流动性"/);
  assert.match(source, /FieldGroup label="最低 FDV"/);
  assert.match(source, /FieldGroup label="最高 FDV"/);
  assert.match(source, /仅看带 Telegram 的项目/);
  assert.match(source, /仅看带 X 的项目/);
  assert.match(source, /仅看带官网的项目/);
  assert.match(source, /仅看 Paid Dex 通知/);
  assert.match(source, /placeholder="输入最低市值"/);
  assert.match(source, /placeholder="输入最高市值"/);
  assert.match(source, /placeholder="输入最低流动性"/);
  assert.match(source, /placeholder="输入最高流动性"/);
  assert.match(source, /placeholder="输入最低 FDV"/);
  assert.match(source, /placeholder="输入最高 FDV"/);
  assert.doesNotMatch(source, /最少持币人数/);
  assert.doesNotMatch(source, /最多持币人数/);
  assert.doesNotMatch(source, /minHolders/);
  assert.doesNotMatch(source, /maxHolders/);
  assert.doesNotMatch(source, /FieldGroup label="来源"/);
  assert.doesNotMatch(source, /placeholder="100000"/);
  assert.doesNotMatch(source, /placeholder="3000000"/);
});

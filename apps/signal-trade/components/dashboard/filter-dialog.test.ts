import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const FILTER_DIALOG_PATH = path.resolve(
  import.meta.dirname,
  'filter-dialog.tsx',
);

test('filter dialog source only keeps supported filter controls', () => {
  const source = readFileSync(FILTER_DIALOG_PATH, 'utf8');

  assert.match(source, /label="链路"/);
  assert.match(source, /label="来源"/);
  assert.match(source, /label="最少持币人数"/);
  assert.match(source, /label="最多持币人数"/);
  assert.match(source, /label="最高市值"/);
  assert.match(source, /仅看 Paid Dex 通知/);

  assert.doesNotMatch(source, /label="策略预设"/);
  assert.doesNotMatch(source, /首推 FDV 上限/);
  assert.doesNotMatch(source, /种子必须是 Paid/);
});

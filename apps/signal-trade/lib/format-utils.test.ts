import assert from 'node:assert/strict';
import test from 'node:test';

import { formatRelativeTime } from './format-utils.ts';

test('formatRelativeTime uses seconds for sub-minute ranges', () => {
  const now = Date.UTC(2026, 3, 5, 12, 0, 45);
  const thirtySecondsAgo = new Date(now - 30_000).toISOString();
  const twelveSecondsLater = new Date(now + 12_000).toISOString();

  assert.equal(formatRelativeTime(thirtySecondsAgo, now), '30s ago');
  assert.equal(formatRelativeTime(twelveSecondsLater, now), '12s later');
});

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const WATCH_UTILS_PATH = path.resolve(import.meta.dirname, 'watch-utils.ts');
const BROWSER_REFRESH_PATH = path.resolve(import.meta.dirname, 'browser-refresh.ts');
const USE_BROWSER_WATCH_PATH = path.resolve(
  import.meta.dirname,
  '../hooks/use-browser-watch.ts',
);

test('front-end watch sources cover ws/http/auto for community, ads, and boosts feeds', () => {
  const watchUtilsSource = readFileSync(WATCH_UTILS_PATH, 'utf8');
  const browserRefreshSource = readFileSync(BROWSER_REFRESH_PATH, 'utf8');
  const useBrowserWatchSource = readFileSync(USE_BROWSER_WATCH_PATH, 'utf8');

  assert.match(watchUtilsSource, /community-takeovers\/latest\/v1/);
  assert.match(watchUtilsSource, /ads\/latest\/v1/);
  assert.match(watchUtilsSource, /token-boosts\/latest\/v1/);
  assert.match(watchUtilsSource, /token-boosts\/top\/v1/);

  assert.match(browserRefreshSource, /community-takeovers\/latest\/v1/);
  assert.match(browserRefreshSource, /ads\/latest\/v1/);
  assert.match(browserRefreshSource, /token-boosts\/latest\/v1/);
  assert.match(browserRefreshSource, /token-boosts\/top\/v1/);

  assert.match(useBrowserWatchSource, /transport === 'auto'/);
  assert.match(useBrowserWatchSource, /transport === 'http'/);
  assert.match(useBrowserWatchSource, /connectBrowserWatch\(sessionId, subscriptions\)/);
});

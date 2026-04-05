import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const WATCH_UTILS_PATH = path.resolve(import.meta.dirname, 'watch-utils.ts');
const BROWSER_REFRESH_PATH = path.resolve(import.meta.dirname, 'browser-refresh.ts');
const PACKAGE_JSON_PATH = path.resolve(import.meta.dirname, '../package.json');
const USE_BROWSER_WATCH_PATH = path.resolve(
  import.meta.dirname,
  '../hooks/use-browser-watch.ts',
);
const USE_DIAGNOSTICS_PATH = path.resolve(
  import.meta.dirname,
  '../hooks/use-diagnostics.ts',
);
const NODE_ONLY_PATHS = [
  path.resolve(import.meta.dirname, '../app/api/runtime/diagnostics/route.ts'),
  path.resolve(import.meta.dirname, '../app/api/notifications/refresh/route.ts'),
  path.resolve(import.meta.dirname, '../scripts/refresh-feed.ts'),
  path.resolve(import.meta.dirname, '../scripts/watch-feed.ts'),
  path.resolve(import.meta.dirname, 'runtime/config.ts'),
  path.resolve(import.meta.dirname, 'runtime/dexscreener.ts'),
  path.resolve(import.meta.dirname, 'runtime/diagnostics.ts'),
  path.resolve(import.meta.dirname, 'runtime/env.ts'),
  path.resolve(import.meta.dirname, 'runtime/paths.ts'),
  path.resolve(import.meta.dirname, 'runtime/proxy-env.ts'),
  path.resolve(import.meta.dirname, 'runtime/refresh-feed.ts'),
  path.resolve(import.meta.dirname, 'runtime/watch-loop.ts'),
];

test('front-end watch sources cover ws/http/auto for community, ads, and boosts feeds', () => {
  const watchUtilsSource = readFileSync(WATCH_UTILS_PATH, 'utf8');
  const browserRefreshSource = readFileSync(BROWSER_REFRESH_PATH, 'utf8');
  const packageJsonSource = readFileSync(PACKAGE_JSON_PATH, 'utf8');
  const useBrowserWatchSource = readFileSync(USE_BROWSER_WATCH_PATH, 'utf8');
  const useDiagnosticsSource = readFileSync(USE_DIAGNOSTICS_PATH, 'utf8');

  assert.match(watchUtilsSource, /community-takeovers\/latest\/v1/);
  assert.match(watchUtilsSource, /ads\/latest\/v1/);
  assert.match(watchUtilsSource, /token-boosts\/latest\/v1/);
  assert.match(watchUtilsSource, /token-boosts\/top\/v1/);

  assert.match(browserRefreshSource, /community-takeovers\/latest\/v1/);
  assert.match(browserRefreshSource, /ads\/latest\/v1/);
  assert.match(browserRefreshSource, /token-boosts\/latest\/v1/);
  assert.match(browserRefreshSource, /token-boosts\/top\/v1/);
  assert.doesNotMatch(browserRefreshSource, /\/api\/runtime\/ingest/);

  assert.match(useBrowserWatchSource, /transport === 'auto'/);
  assert.match(useBrowserWatchSource, /transport === 'http'/);
  assert.match(useBrowserWatchSource, /connectBrowserWatch\(sessionId, subscriptions\)/);
  assert.doesNotMatch(useBrowserWatchSource, /\/api\/runtime\/ingest/);
  assert.doesNotMatch(useDiagnosticsSource, /\/api\/runtime\/diagnostics/);
  assert.doesNotMatch(packageJsonSource, /runtime:refresh/);
  assert.doesNotMatch(packageJsonSource, /runtime:watch/);

  for (const nodeOnlyPath of NODE_ONLY_PATHS) {
    assert.equal(
      existsSync(nodeOnlyPath),
      false,
      `${path.relative(process.cwd(), nodeOnlyPath)} should be removed`,
    );
  }
});

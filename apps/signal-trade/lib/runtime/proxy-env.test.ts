import assert from 'node:assert/strict';
import test from 'node:test';

import { withProxyEnvDisabled } from './proxy-env.ts';

const PROXY_KEYS = [
  'HTTP_PROXY',
  'HTTPS_PROXY',
  'ALL_PROXY',
  'http_proxy',
  'https_proxy',
  'all_proxy',
] as const;

test('temporarily clears proxy env and restores it after async work', async () => {
  const original = snapshotProxyEnv();

  setProxyEnv('http://127.0.0.1:7897');

  await withProxyEnvDisabled(async () => {
    for (const key of PROXY_KEYS) {
      assert.equal(process.env[key], undefined);
    }
  });

  for (const key of PROXY_KEYS) {
    assert.equal(process.env[key], 'http://127.0.0.1:7897');
  }

  restoreProxyEnv(original);
});

test('nested calls do not restore proxy env before the outer call finishes', async () => {
  const original = snapshotProxyEnv();

  setProxyEnv('http://127.0.0.1:7897');

  await withProxyEnvDisabled(async () => {
    await withProxyEnvDisabled(async () => {
      for (const key of PROXY_KEYS) {
        assert.equal(process.env[key], undefined);
      }
    });

    for (const key of PROXY_KEYS) {
      assert.equal(process.env[key], undefined);
    }
  });

  for (const key of PROXY_KEYS) {
    assert.equal(process.env[key], 'http://127.0.0.1:7897');
  }

  restoreProxyEnv(original);
});

function snapshotProxyEnv(): Record<string, string | undefined> {
  return Object.fromEntries(PROXY_KEYS.map(key => [key, process.env[key]]));
}

function restoreProxyEnv(snapshot: Record<string, string | undefined>): void {
  for (const key of PROXY_KEYS) {
    const value = snapshot[key];
    if (typeof value === 'string') {
      process.env[key] = value;
      continue;
    }

    delete process.env[key];
  }
}

function setProxyEnv(value: string): void {
  for (const key of PROXY_KEYS) {
    process.env[key] = value;
  }
}

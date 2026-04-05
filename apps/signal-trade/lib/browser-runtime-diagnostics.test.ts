import assert from 'node:assert/strict';
import test from 'node:test';

import { runBrowserRuntimeDiagnostics } from './browser-runtime-diagnostics.ts';

test('runs browser diagnostics without posting to a runtime route', async () => {
  const fetchCalls: string[] = [];

  const diagnostics = await runBrowserRuntimeDiagnostics({
    fetcher: async input => {
      fetchCalls.push(String(input));
      return {
        ok: true,
        status: 200,
      } as Response;
    },
    webSocketFactory: url => new SuccessfulWebSocket(url) as unknown as WebSocket,
  });

  assert.equal(diagnostics.notificationsStore.mode, 'none');
  assert.deepEqual(diagnostics.proxyEnv, {});
  assert.equal(diagnostics.httpCheck.ok, true);
  assert.equal(diagnostics.httpCheck.statusCode, 200);
  assert.equal(diagnostics.wsCheck.ok, true);
  assert.equal(diagnostics.wsCheck.closeCode, 1000);
  assert.deepEqual(fetchCalls, ['https://api.dexscreener.com/token-profiles/latest/v1']);
});

class SuccessfulWebSocket {
  public readonly url: string;
  public readyState = 0;
  private readonly listeners = new Map<string, Set<(event: unknown) => void>>();

  constructor(url: string) {
    this.url = url;

    queueMicrotask(() => {
      this.readyState = 1;
      this.emit('open', {});
    });
  }

  addEventListener(type: string, listener: (event: unknown) => void): void {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set());
    }

    this.listeners.get(type)!.add(listener);
  }

  removeEventListener(type: string, listener: (event: unknown) => void): void {
    this.listeners.get(type)?.delete(listener);
  }

  close(code = 1000, reason = ''): void {
    this.readyState = 3;
    this.emit('close', { code, reason });
  }

  private emit(type: string, event: unknown): void {
    for (const listener of this.listeners.get(type) ?? []) {
      listener(event);
    }
  }
}

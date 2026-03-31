import { signalTradeConfig } from '@/lib/runtime/config';
import { getNotificationStoreStats } from '@/lib/runtime/notification-store';
import type {
  RuntimeDiagnosticsNotificationStore,
  RuntimeDiagnosticsResult,
  RuntimeNetworkCheck,
} from '@/lib/types';

const DEX_HTTP_TARGET = 'https://api.dexscreener.com/token-profiles/latest/v1';
const DEX_WS_TARGET = 'wss://api.dexscreener.com/token-profiles/latest/v1';

export async function runRuntimeDiagnostics(): Promise<RuntimeDiagnosticsResult> {
  const [notificationsStore, httpCheck, wsCheck] = await Promise.all([
    inspectNotificationsStore(),
    runHttpCheck(),
    runWsCheck(),
  ]);

  return {
    checkedAt: new Date().toISOString(),
    httpCheck,
    notificationsStore,
    proxyEnv: collectProxyEnv(),
    wsCheck,
  };
}

async function inspectNotificationsStore(): Promise<RuntimeDiagnosticsNotificationStore> {
  return getNotificationStoreStats();
}

async function runHttpCheck(): Promise<RuntimeNetworkCheck> {
  const startedAt = Date.now();
  const timeoutMs = Math.max(
    Math.min(signalTradeConfig.dexscreener.requestTimeoutSec * 1000, 15_000),
    3_000,
  );

  try {
    const response = await fetch(DEX_HTTP_TARGET, {
      headers: {
        Accept: 'application/json',
      },
      next: { revalidate: 0 },
      signal: AbortSignal.timeout(timeoutMs),
    });

    return {
      detail: `status=${response.status}`,
      durationMs: Date.now() - startedAt,
      error: response.ok ? null : `HTTP ${response.status}`,
      ok: response.ok,
      status: response.ok ? 'ok' : 'error',
      statusCode: response.status,
      target: DEX_HTTP_TARGET,
    };
  } catch (error) {
    return {
      detail: null,
      durationMs: Date.now() - startedAt,
      error: formatError(error),
      ok: false,
      status: isTimeoutError(error) ? 'timeout' : 'error',
      statusCode: null,
      target: DEX_HTTP_TARGET,
    };
  }
}

async function runWsCheck(): Promise<RuntimeNetworkCheck> {
  const startedAt = Date.now();
  const timeoutMs = Math.max(
    Math.min(signalTradeConfig.dexscreener.requestTimeoutSec * 1000, 15_000),
    3_000,
  );

  return await new Promise(resolve => {
    let settled = false;
    let sawError = false;

    const socket = new WebSocket(DEX_WS_TARGET);

    const finalize = (result: RuntimeNetworkCheck): void => {
      if (settled) {
        return;
      }

      settled = true;
      clearTimeout(timer);
      socket.removeEventListener('open', handleOpen);
      socket.removeEventListener('error', handleError);
      socket.removeEventListener('close', handleClose);
      resolve(result);
    };

    const timer = setTimeout(() => {
      safeClose(socket, 1000, 'diagnostic_timeout');
      finalize({
        closeCode: null,
        detail: null,
        durationMs: Date.now() - startedAt,
        error: `timeout after ${timeoutMs}ms`,
        ok: false,
        status: 'timeout',
        target: DEX_WS_TARGET,
      });
    }, timeoutMs);

    const handleOpen = (): void => {
      safeClose(socket, 1000, 'diagnostic_complete');
      finalize({
        closeCode: 1000,
        detail: 'connection opened',
        durationMs: Date.now() - startedAt,
        error: null,
        ok: true,
        status: 'ok',
        target: DEX_WS_TARGET,
      });
    };

    const handleError = (): void => {
      sawError = true;
    };

    const handleClose = (event: CloseEvent): void => {
      finalize({
        closeCode: event.code,
        detail: event.reason || null,
        durationMs: Date.now() - startedAt,
        error:
          event.code === 1000 && !sawError
            ? null
            : `socket closed with code ${event.code}${sawError ? ' after transport error' : ''}`,
        ok: event.code === 1000 && !sawError,
        status: event.code === 1000 && !sawError ? 'ok' : 'error',
        target: DEX_WS_TARGET,
      });
    };

    socket.addEventListener('open', handleOpen);
    socket.addEventListener('error', handleError);
    socket.addEventListener('close', handleClose);
  });
}

function collectProxyEnv(): Record<string, string> {
  const keys = [
    'HTTP_PROXY',
    'HTTPS_PROXY',
    'ALL_PROXY',
    'NO_PROXY',
    'http_proxy',
    'https_proxy',
    'all_proxy',
    'no_proxy',
  ] as const;

  const proxyEnv: Record<string, string> = {};
  for (const key of keys) {
    const value = process.env[key];
    if (typeof value === 'string' && value.trim()) {
      proxyEnv[key] = value.trim();
    }
  }

  return proxyEnv;
}

function formatError(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message.trim();
  }
  return 'Unknown network error';
}

function isTimeoutError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }
  return (
    error.name === 'TimeoutError' ||
    error.message.toLowerCase().includes('timeout')
  );
}

function safeClose(socket: WebSocket, code: number, reason: string): void {
  if (
    socket.readyState === WebSocket.CLOSING ||
    socket.readyState === WebSocket.CLOSED
  ) {
    return;
  }

  try {
    socket.close(code, reason);
  } catch {
    socket.close();
  }
}

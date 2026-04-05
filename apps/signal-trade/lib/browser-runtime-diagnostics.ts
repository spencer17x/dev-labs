import type { RuntimeDiagnosticsResult, RuntimeNetworkCheck } from './types';

const DEX_HTTP_TARGET = 'https://api.dexscreener.com/token-profiles/latest/v1';
const DEX_WS_TARGET = 'wss://api.dexscreener.com/token-profiles/latest/v1';
const BROWSER_DIAGNOSTICS_TIMEOUT_MS = 12_000;

type DiagnosticsFetcher = (
  input: string | URL | Request,
  init?: RequestInit,
) => Promise<Pick<Response, 'ok' | 'status'>>;

type BrowserWebSocketLike = Pick<
  WebSocket,
  'addEventListener' | 'close' | 'readyState' | 'removeEventListener'
>;

export type BrowserRuntimeDiagnosticsOptions = {
  fetcher?: DiagnosticsFetcher;
  timeoutMs?: number;
  webSocketFactory?: (url: string) => BrowserWebSocketLike;
};

export async function runBrowserRuntimeDiagnostics(
  options: BrowserRuntimeDiagnosticsOptions = {},
): Promise<RuntimeDiagnosticsResult> {
  const timeoutMs =
    typeof options.timeoutMs === 'number' && options.timeoutMs > 0
      ? Math.trunc(options.timeoutMs)
      : BROWSER_DIAGNOSTICS_TIMEOUT_MS;

  const [httpCheck, wsCheck] = await Promise.all([
    runHttpCheck(options.fetcher ?? fetch, timeoutMs),
    runWsCheck(resolveWebSocketFactory(options.webSocketFactory), timeoutMs),
  ]);

  return {
    checkedAt: new Date().toISOString(),
    httpCheck,
    notificationsStore: {
      count: 0,
      isEmpty: true,
      mode: 'none',
      resetsOnRestart: false,
    },
    proxyEnv: {},
    wsCheck,
  };
}

async function runHttpCheck(
  fetcher: DiagnosticsFetcher,
  timeoutMs: number,
): Promise<RuntimeNetworkCheck> {
  const startedAt = Date.now();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetcher(DEX_HTTP_TARGET, {
      cache: 'no-store',
      headers: {
        Accept: 'application/json',
      },
      signal: controller.signal,
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
  } finally {
    clearTimeout(timer);
  }
}

async function runWsCheck(
  webSocketFactory: ((url: string) => BrowserWebSocketLike) | null,
  timeoutMs: number,
): Promise<RuntimeNetworkCheck> {
  if (!webSocketFactory) {
    return {
      closeCode: null,
      detail: null,
      durationMs: 0,
      error: 'WebSocket unavailable in current environment',
      ok: false,
      status: 'error',
      target: DEX_WS_TARGET,
    };
  }

  const startedAt = Date.now();

  return await new Promise(resolve => {
    let settled = false;
    let sawError = false;
    const socket = webSocketFactory(DEX_WS_TARGET);

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

    const handleClose = (event: Event): void => {
      const closeEvent = event as CloseEvent;
      const closeCode =
        typeof closeEvent.code === 'number' ? closeEvent.code : null;
      const reason =
        typeof closeEvent.reason === 'string' && closeEvent.reason.trim()
          ? closeEvent.reason.trim()
          : null;

      finalize({
        closeCode,
        detail: reason,
        durationMs: Date.now() - startedAt,
        error:
          closeCode === 1000 && !sawError
            ? null
            : `socket closed with code ${closeCode ?? 'unknown'}${
                sawError ? ' after transport error' : ''
              }`,
        ok: closeCode === 1000 && !sawError,
        status: closeCode === 1000 && !sawError ? 'ok' : 'error',
        target: DEX_WS_TARGET,
      });
    };

    socket.addEventListener('open', handleOpen);
    socket.addEventListener('error', handleError);
    socket.addEventListener('close', handleClose);
  });
}

function resolveWebSocketFactory(
  webSocketFactory: BrowserRuntimeDiagnosticsOptions['webSocketFactory'],
): ((url: string) => BrowserWebSocketLike) | null {
  if (webSocketFactory) {
    return webSocketFactory;
  }

  if (typeof WebSocket === 'function') {
    return url => new WebSocket(url);
  }

  return null;
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
    error.name === 'AbortError' ||
    error.name === 'TimeoutError' ||
    error.message.toLowerCase().includes('timeout')
  );
}

function safeClose(
  socket: BrowserWebSocketLike,
  code: number,
  reason: string,
): void {
  if (socket.readyState === 2 || socket.readyState === 3) {
    return;
  }

  try {
    socket.close(code, reason);
  } catch {
    socket.close();
  }
}

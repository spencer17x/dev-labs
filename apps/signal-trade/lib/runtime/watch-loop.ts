import {
  normalizeDexSubscriptions,
  watchDexSubscriptions,
  type DexScreenerSubscription,
  type DexStreamStatusEvent,
} from '@/lib/runtime/dexscreener';
import { signalTradeConfig } from '@/lib/runtime/config';
import {
  ingestSignalEvents,
  refreshNotificationFeed,
} from '@/lib/runtime/refresh-feed';
import type { WatchTransport } from '@/lib/types';

type WatchLoopOptions = {
  intervalSec?: number;
  limit?: number;
  onLog?: (message: string) => void;
  onStatus?: (status: DexStreamStatusEvent) => void;
  signal: AbortSignal;
  subscriptions?: string[];
  transport?: WatchTransport;
};

export async function runWatchLoop(options: WatchLoopOptions): Promise<void> {
  const subscriptions = normalizeDexSubscriptions(options.subscriptions);
  const transport = normalizeWatchTransport(options.transport);
  const intervalMs =
    (typeof options.intervalSec === 'number'
      ? options.intervalSec
      : signalTradeConfig.dexscreener.pollIntervalSec) * 1000;

  options.onLog?.(
    `[signal-trade] watch starting transport=${transport} subscriptions=${subscriptions.join(
      ',',
    )} limit=${options.limit ?? 'default'} intervalSec=${Math.round(intervalMs / 1000)}`,
  );

  if (transport === 'http') {
    await runHttpWatch({
      signal: options.signal,
      subscriptions,
      limit: options.limit,
      intervalMs,
      onLog: options.onLog,
    });
    return;
  }

  await runWsWatch({
    signal: options.signal,
    subscriptions,
    limit: options.limit,
    intervalMs,
    onLog: options.onLog,
    onStatus: options.onStatus,
    restFallback: transport === 'auto',
  });
}

export function normalizeWatchTransport(
  value: string | undefined,
): WatchTransport {
  return value === 'http' || value === 'ws' || value === 'auto' ? value : 'auto';
}

async function runHttpWatch({
  signal,
  subscriptions,
  limit,
  intervalMs,
  onLog,
}: {
  signal: AbortSignal;
  subscriptions: DexScreenerSubscription[];
  limit?: number;
  intervalMs: number;
  onLog?: (message: string) => void;
}): Promise<void> {
  while (!signal.aborted) {
    try {
      const result = await refreshNotificationFeed({
        limit,
        subscriptions,
      });
      onLog?.(
        `[signal-trade] http processed=${result.processed} stored=${result.stored} generatedAt=${result.generatedAt}`,
      );
    } catch (error) {
      onLog?.(
        `[signal-trade] http refresh failed ${
          error instanceof Error ? error.message : 'Unknown refresh error'
        }`,
      );
    }

    await sleep(intervalMs, signal);
  }
}

async function runWsWatch({
  signal,
  subscriptions,
  limit,
  intervalMs,
  onLog,
  onStatus,
  restFallback,
}: {
  signal: AbortSignal;
  subscriptions: DexScreenerSubscription[];
  limit?: number;
  intervalMs: number;
  onLog?: (message: string) => void;
  onStatus?: (status: DexStreamStatusEvent) => void;
  restFallback: boolean;
}): Promise<void> {
  const taskQueue = createTaskQueue(onLog);
  const lastFallbackAt = new Map<DexScreenerSubscription, number>();

  await watchDexSubscriptions({
    subscriptions,
    limit,
    signal,
    onEvents: async (events, subscription) => {
      await taskQueue.queue(async () => {
        const result = await ingestSignalEvents(events);
        onLog?.(
          `[signal-trade] ws subscription=${subscription} processed=${result.processed} stored=${result.stored}`,
        );
      });
    },
    onStatus: status => {
      onStatus?.(status);
      logStatus(status, onLog);

      if (
        restFallback &&
        (status.type === 'error' ||
          status.type === 'stale' ||
          status.type === 'reconnecting')
      ) {
        maybeScheduleRestFallback({
          fallbackIntervalMs: intervalMs,
          lastFallbackAt,
          limit,
          onLog,
          queue: taskQueue.queue,
          status,
        });
      }
    },
  });

  await taskQueue.flush();
}

function createTaskQueue(
  onLog?: (message: string) => void,
): {
  flush: () => Promise<void>;
  queue: (task: () => Promise<void>) => Promise<void>;
} {
  let pending = Promise.resolve();

  return {
    queue(task) {
      pending = pending.then(task).catch(error => {
        onLog?.(
          `[signal-trade] queue error ${
            error instanceof Error ? error.message : 'Unknown queue error'
          }`,
        );
      });
      return pending;
    },
    flush() {
      return pending;
    },
  };
}

function logStatus(
  status: DexStreamStatusEvent,
  onLog?: (message: string) => void,
): void {
  switch (status.type) {
    case 'connecting':
      onLog?.(`[signal-trade] ws connecting subscription=${status.subscription}`);
      return;
    case 'open':
      onLog?.(`[signal-trade] ws open subscription=${status.subscription}`);
      return;
    case 'reconnecting':
      onLog?.(
        `[signal-trade] ws reconnecting subscription=${status.subscription} ${
          status.detail ?? ''
        }`.trim(),
      );
      return;
    case 'stale':
    case 'error':
      onLog?.(
        `[signal-trade] ws ${status.type} subscription=${status.subscription} ${
          status.detail ?? ''
        }`.trim(),
      );
      return;
    case 'closed':
      onLog?.(
        `[signal-trade] ws closed subscription=${status.subscription} ${
          status.detail ?? ''
        }`.trim(),
      );
      return;
  }
}

function maybeScheduleRestFallback({
  fallbackIntervalMs,
  lastFallbackAt,
  limit,
  onLog,
  queue,
  status,
}: {
  fallbackIntervalMs: number;
  lastFallbackAt: Map<DexScreenerSubscription, number>;
  limit?: number;
  onLog?: (message: string) => void;
  queue: (task: () => Promise<void>) => Promise<void>;
  status: DexStreamStatusEvent;
}): void {
  const lastRunAt = lastFallbackAt.get(status.subscription) ?? 0;
  const now = Date.now();
  if (now - lastRunAt < fallbackIntervalMs) {
    return;
  }

  lastFallbackAt.set(status.subscription, now);

  void queue(async () => {
    onLog?.(
      `[signal-trade] rest fallback subscription=${status.subscription} intervalMs=${fallbackIntervalMs}`,
    );

    try {
      const result = await refreshNotificationFeed({
        limit,
        subscriptions: [status.subscription],
      });
      onLog?.(
        `[signal-trade] rest fallback subscription=${status.subscription} processed=${result.processed} stored=${result.stored}`,
      );
    } catch (error) {
      onLog?.(
        `[signal-trade] rest fallback failed subscription=${status.subscription} ${
          error instanceof Error ? error.message : 'Unknown fallback error'
        }`,
      );
    }
  });
}

async function sleep(ms: number, signal: AbortSignal): Promise<void> {
  if (signal.aborted) {
    return;
  }

  await new Promise<void>(resolve => {
    const timer = setTimeout(() => {
      signal.removeEventListener('abort', handleAbort);
      resolve();
    }, ms);

    const handleAbort = (): void => {
      clearTimeout(timer);
      signal.removeEventListener('abort', handleAbort);
      resolve();
    };

    signal.addEventListener('abort', handleAbort, { once: true });
  });
}

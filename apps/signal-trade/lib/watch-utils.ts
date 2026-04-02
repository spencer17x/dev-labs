import {
  DEFAULT_DEX_WATCH_SUBSCRIPTIONS,
  getDexWatchSubscriptionLabel,
} from '@/lib/dexscreener-subscriptions';
import type { RuntimeDiagnosticsResult, WatchRuntimeState } from '@/lib/types';
import { padNumber } from '@/lib/format-utils';

export const WATCH_INTERVAL_SEC = 15;
export const WATCH_LIMIT = 10;
export const BROWSER_WS_CONNECT_TIMEOUT_MS = 15_000;
export const BROWSER_WS_STALE_TIMEOUT_MS = 60_000;
export const BROWSER_WS_RECONNECT_DELAY_MS = 3_000;

export function formatWatchStatus(watchRuntime: WatchRuntimeState): string {
  if (hasWatchConnectionIssue(watchRuntime)) {
    if (
      watchRuntime.lastStatus === 'connecting' ||
      watchRuntime.lastStatus === 'reconnecting'
    ) {
      return '连接失败，正在重试';
    }

    return '连接异常';
  }

  switch (watchRuntime.lastStatus) {
    case 'connecting':
      return '连接中';
    case 'open':
      return '已连接';
    case 'reconnecting':
      return '重连中';
    case 'stale':
      return '连接超时';
    case 'error':
      return '异常';
    case 'closed':
      return '已关闭';
    case 'starting':
      return '启动中';
    case 'stopped':
      return '已停止';
    case 'idle':
      return '空闲';
    default:
      return watchRuntime.lastStatus;
  }
}

export function formatWatchSubscriptions(subscriptions: string[]): string {
  return subscriptions.map(getDexWatchSubscriptionLabel).join(', ');
}

export function hasWatchConnectionIssue(watchRuntime: WatchRuntimeState): boolean {
  if (!watchRuntime.running) {
    return watchRuntime.lastStatus === 'error' || watchRuntime.lastStatus === 'stale';
  }

  return Boolean(watchRuntime.lastError) || watchRuntime.lastStatus === 'error' || watchRuntime.lastStatus === 'stale';
}

export function formatNotificationStore(
  notificationsStore: RuntimeDiagnosticsResult['notificationsStore'],
): string {
  if (notificationsStore.mode === 'none') {
    return '未启用服务端通知存储，数据只存在于当前浏览器会话';
  }

  if (notificationsStore.isEmpty) {
    return '当前没有服务端通知记录';
  }

  return `当前记录 ${notificationsStore.count} 条`;
}

export function formatNetworkCheck(
  check: RuntimeDiagnosticsResult['httpCheck'],
): string {
  const duration = formatDurationMs(check.durationMs);
  if (check.ok) {
    const detail = check.statusCode ? `HTTP ${check.statusCode}` : check.detail;
    return `${detail ?? 'ok'}，耗时 ${duration}`;
  }

  if (check.closeCode !== undefined && check.closeCode !== null) {
    return `${check.status.toUpperCase()}，close code=${check.closeCode}，耗时 ${duration}${
      check.error ? `，${check.error}` : ''
    }`;
  }

  return `${check.status.toUpperCase()}，耗时 ${duration}${
    check.error ? `，${check.error}` : ''
  }`;
}

export function formatDurationMs(value: number): string {
  if (!Number.isFinite(value) || value < 0) {
    return 'n/a';
  }

  if (value < 1000) {
    return `${value}ms`;
  }

  return `${(value / 1000).toFixed(1)}s`;
}

export function formatAbsoluteTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return 'unknown';
  }

  return [
    date.getFullYear(),
    padNumber(date.getMonth() + 1),
    padNumber(date.getDate()),
  ].join('-')
    .concat(
      ` ${padNumber(date.getHours())}:${padNumber(date.getMinutes())}:${padNumber(
        date.getSeconds(),
      )}`,
    );
}

export function createBrowserWatchState(
  overrides: Partial<WatchRuntimeState> = {},
): WatchRuntimeState {
  return {
    intervalSec: WATCH_INTERVAL_SEC,
    lastActivityAt: null,
    lastError: null,
    lastStartedAt: null,
    lastStatus: 'idle',
    lastStatusDetail: null,
    limit: WATCH_LIMIT,
    running: false,
    subscriptions: [...DEFAULT_DEX_WATCH_SUBSCRIPTIONS],
    transport: 'auto',
    ...overrides,
  };
}

export function buildDexSubscriptionWsUrl(subscription: string, limit: number): string {
  const endpoint =
    subscription === 'community_takeovers_latest'
      ? '/community-takeovers/latest/v1'
      : subscription === 'ads_latest'
        ? '/ads/latest/v1'
        : subscription === 'token_boosts_latest'
          ? '/token-boosts/latest/v1'
          : subscription === 'token_boosts_top'
            ? '/token-boosts/top/v1'
            : '/token-profiles/latest/v1';

  const url = new URL(endpoint, 'wss://api.dexscreener.com');
  if (limit > 0) {
    url.searchParams.set('limit', String(limit));
  }
  return url.toString();
}

export async function readBrowserWsMessageText(data: unknown): Promise<string | null> {
  if (typeof data === 'string') {
    return data;
  }
  if (data instanceof ArrayBuffer) {
    return new TextDecoder().decode(data);
  }
  if (ArrayBuffer.isView(data)) {
    return new TextDecoder().decode(data);
  }
  if (typeof Blob !== 'undefined' && data instanceof Blob) {
    return await data.text();
  }
  return null;
}

export function clearBrowserTimerMap(
  timers: Map<string, number>,
  subscription?: string,
): void {
  if (subscription) {
    const timer = timers.get(subscription);
    if (timer !== undefined) {
      window.clearTimeout(timer);
      timers.delete(subscription);
    }
    return;
  }

  for (const timer of timers.values()) {
    window.clearTimeout(timer);
  }
  timers.clear();
}

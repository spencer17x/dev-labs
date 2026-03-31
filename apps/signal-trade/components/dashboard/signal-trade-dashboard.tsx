'use client';

import type { JSX, ReactNode } from 'react';
import {
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import type { LucideIcon } from 'lucide-react';
import {
  Activity,
  ArrowUpRight,
  BellRing,
  Filter,
  Layers,
  LoaderCircle,
  RefreshCw,
  Search,
  Target,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  DEFAULT_DEX_WATCH_SUBSCRIPTIONS,
  DEX_WATCH_SUBSCRIPTION_OPTIONS,
  getDexWatchSubscriptionLabel,
} from '@/lib/dexscreener-subscriptions';
import type {
  DashboardFilters,
  NotificationRecord,
  RuntimeDiagnosticsResult,
  RuntimeRefreshResult,
  WatchRuntimeState,
} from '@/lib/types';
import { cn } from '@/lib/utils';

type DashboardProps = {
  initialFilters: DashboardFilters;
  initialNow: number;
  initialNotifications: NotificationRecord[];
};

type RefreshState = 'idle' | 'syncing' | 'synced' | 'error';
type RuntimeIngestResult = {
  message?: string;
  notifications?: NotificationRecord[];
  processed?: number;
  stored?: number;
};

const WATCH_INTERVAL_SEC = 15;
const WATCH_LIMIT = 10;
const MAX_SESSION_NOTIFICATIONS = 250;
const BROWSER_WS_CONNECT_TIMEOUT_MS = 15_000;
const BROWSER_WS_STALE_TIMEOUT_MS = 60_000;
const BROWSER_WS_RECONNECT_DELAY_MS = 3_000;

export function SignalTradeDashboard({
  initialFilters,
  initialNow,
  initialNotifications,
}: DashboardProps): JSX.Element {
  const [filters, setFilters] = useState<DashboardFilters>(initialFilters);
  const [notifications, setNotifications] =
    useState<NotificationRecord[]>(initialNotifications);
  const [relativeNow, setRelativeNow] = useState(initialNow);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isWatchMutating, setIsWatchMutating] = useState(false);
  const [isDiagnosing, setIsDiagnosing] = useState(false);
  const [refreshState, setRefreshState] = useState<RefreshState>('idle');
  const [refreshSummary, setRefreshSummary] = useState('');
  const [diagnostics, setDiagnostics] = useState<RuntimeDiagnosticsResult | null>(
    null,
  );
  const [diagnosticsError, setDiagnosticsError] = useState('');
  const [watchRuntime, setWatchRuntime] = useState<WatchRuntimeState | null>(null);
  const browserConnectTimersRef = useRef(new Map<string, number>());
  const browserReconnectTimersRef = useRef(new Map<string, number>());
  const browserStaleTimersRef = useRef(new Map<string, number>());
  const browserHttpIntervalRef = useRef<number | null>(null);
  const browserProcessingRef = useRef<Promise<void>>(Promise.resolve());
  const browserSessionRef = useRef(0);
  const browserSocketsRef = useRef(new Map<string, WebSocket>());
  const watchRuntimeRef = useRef<WatchRuntimeState | null>(null);

  const deferredSearch = useDeferredValue(filters.search);
  const deferredWatchTerms = useDeferredValue(filters.watchTerms);

  useEffect(() => {
    setRelativeNow(Date.now());

    const timer = window.setInterval(() => {
      setRelativeNow(Date.now());
    }, 60_000);

    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    watchRuntimeRef.current = watchRuntime;
  }, [watchRuntime]);

  useEffect(() => {
    return () => {
      teardownBrowserWatch();
    };
  }, []);

  const chainOptions = useMemo(
    () => uniqueValues(notifications.map(record => record.event.chain ?? '')),
    [notifications],
  );

  const sourceOptions = useMemo(
    () =>
      uniqueValues(
        notifications.map(
          record => `${record.event.source}.${record.event.subtype}`,
        ),
      ),
    [notifications],
  );

  const selectedWatchSubscriptions = useMemo(
    () => getSelectedWatchSubscriptions(filters.watchSubscriptions),
    [filters.watchSubscriptions],
  );

  const filteredNotifications = useMemo(() => {
    const search = deferredSearch.trim().toLowerCase();
    const watchTerms = parseListFilter(deferredWatchTerms);
    const minHolders = parseNumericFilter(filters.minHolders);
    const maxHolders = parseNumericFilter(filters.maxHolders);
    const maxMarketCap = parseNumericFilter(filters.maxMarketCap);
    const minCommunityCount = parseNumericFilter(filters.minCommunityCount);
    return notifications
      .filter(record => {
        const sourceKey = `${record.event.source}.${record.event.subtype}`;
        const searchHaystack = [
          record.context.token?.symbol,
          record.context.token?.name,
          record.context.token?.address,
          record.event.token.symbol,
          record.event.token.name,
          record.event.token.address,
          record.event.author?.display_name,
          record.message,
          record.context.dexscreener?.header,
          record.context.dexscreener?.description,
          record.summary.twitterUsername,
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase();

        if (filters.chain !== 'all' && record.event.chain !== filters.chain) {
          return false;
        }
        if (filters.source !== 'all' && sourceKey !== filters.source) {
          return false;
        }
        if (filters.paidOnly && !record.summary.paid) {
          return false;
        }
        if (search && !searchHaystack.includes(search)) {
          return false;
        }
        if (
          minHolders !== null &&
          (record.summary.holderCount ?? Number.NEGATIVE_INFINITY) < minHolders
        ) {
          return false;
        }
        if (
          maxHolders !== null &&
          (record.summary.holderCount ?? Number.POSITIVE_INFINITY) > maxHolders
        ) {
          return false;
        }
        if (
          maxMarketCap !== null &&
          (record.summary.marketCap ?? Number.POSITIVE_INFINITY) > maxMarketCap
        ) {
          return false;
        }
        if (
          minCommunityCount !== null &&
          (record.summary.communityCount ?? Number.NEGATIVE_INFINITY) < minCommunityCount
        ) {
          return false;
        }
        if (
          watchTerms.length > 0 &&
          !watchTerms.some(term => searchHaystack.includes(term))
        ) {
          return false;
        }
        return true;
      })
      .sort(
        (left, right) =>
          new Date(right.notifiedAt).getTime() - new Date(left.notifiedAt).getTime(),
      );
  }, [
    deferredSearch,
    deferredWatchTerms,
    filters.chain,
    filters.maxMarketCap,
    filters.minCommunityCount,
    filters.maxHolders,
    filters.minHolders,
    filters.paidOnly,
    filters.source,
    notifications,
  ]);

  function appendNotifications(nextNotifications: NotificationRecord[]): void {
    if (nextNotifications.length === 0) {
      return;
    }

    setNotifications(current => mergeNotifications(current, nextNotifications));
  }

  async function syncNotifications(): Promise<void> {
    setIsRefreshing(true);
    setRefreshState('syncing');
    setRefreshSummary('');

    try {
      if (selectedWatchSubscriptions.length === 0) {
        throw new Error('请至少选择一个订阅');
      }

      const response = await fetch('/api/notifications/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          limit: WATCH_LIMIT,
          subscriptions: selectedWatchSubscriptions,
        }),
      });
      const payload = (await response.json().catch(() => ({}))) as Partial<
        RuntimeRefreshResult
      > & {
        message?: string;
      };
      if (!response.ok) {
        throw new Error(
          typeof payload.message === 'string' && payload.message.trim()
            ? payload.message.trim()
            : `unexpected status ${response.status}`,
        );
      }
      const nextNotifications = Array.isArray(payload.notifications)
        ? payload.notifications
        : [];

      appendNotifications(nextNotifications);
      setRefreshState('synced');
      setRefreshSummary(
        `本次扫描 ${payload.processed ?? 0} 条事件，接收 ${payload.stored ?? 0} 条通知。`,
      );
    } catch (error) {
      setRefreshState('error');
      setRefreshSummary(
        `同步失败：${error instanceof Error ? error.message : '请检查网络连通性和本地运行配置。'}`,
      );
    } finally {
      setIsRefreshing(false);
    }
  }

  function setBrowserWatchState(
    sessionId: number,
    updater: (current: WatchRuntimeState) => WatchRuntimeState,
  ): void {
    setWatchRuntime(current => {
      if (browserSessionRef.current !== sessionId) {
        return current;
      }

      return updater(current ?? createBrowserWatchState());
    });
  }

  function clearBrowserHttpInterval(): void {
    if (browserHttpIntervalRef.current === null) {
      return;
    }

    window.clearInterval(browserHttpIntervalRef.current);
    browserHttpIntervalRef.current = null;
  }

  function clearBrowserWatchTimers(subscription?: string): void {
    clearBrowserTimerMap(browserConnectTimersRef.current, subscription);
    clearBrowserTimerMap(browserReconnectTimersRef.current, subscription);
    clearBrowserTimerMap(browserStaleTimersRef.current, subscription);
  }

  function teardownBrowserWatch(): void {
    browserSessionRef.current += 1;
    clearBrowserHttpInterval();
    clearBrowserWatchTimers();
    browserProcessingRef.current = Promise.resolve();

    for (const socket of browserSocketsRef.current.values()) {
      if (
        socket.readyState === WebSocket.CONNECTING ||
        socket.readyState === WebSocket.OPEN
      ) {
        socket.close(1000, 'stopped');
      }
    }
    browserSocketsRef.current.clear();
  }

  function stopBrowserWatch(): void {
    teardownBrowserWatch();
    setWatchRuntime(null);
  }

  async function runBrowserHttpRefresh(
    sessionId: number,
    subscriptions: string[],
    reason: 'fallback' | 'interval' | 'start',
    transport: 'auto' | 'http',
  ): Promise<void> {
    if (browserSessionRef.current !== sessionId) {
      return;
    }

    const currentRuntime = watchRuntimeRef.current;
    if (
      transport === 'auto' &&
      reason === 'interval' &&
      currentRuntime?.running &&
      currentRuntime.lastStatus === 'open' &&
      !currentRuntime.lastError
    ) {
      return;
    }

    const detailPrefix = transport === 'auto' ? 'HTTP fallback' : 'HTTP polling';

    setBrowserWatchState(sessionId, current => ({
      ...current,
      lastStatus:
        transport === 'http' && current.lastStatus !== 'open'
          ? 'connecting'
          : current.lastStatus,
      lastStatusDetail:
        reason === 'start' ? `${detailPrefix} starting` : `${detailPrefix} running`,
      running: true,
      subscriptions: [...subscriptions],
    }));

    const response = await fetch('/api/notifications/refresh', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        limit: WATCH_LIMIT,
        subscriptions,
      }),
    });

    const payload = (await response.json().catch(() => ({}))) as Partial<
      RuntimeRefreshResult
    > & {
      message?: string;
    };

    if (!response.ok) {
      throw new Error(
        typeof payload.message === 'string' && payload.message.trim()
          ? payload.message.trim()
          : `unexpected status ${response.status}`,
      );
    }

    if (browserSessionRef.current !== sessionId) {
      return;
    }

    const nextNotifications = Array.isArray(payload.notifications)
      ? payload.notifications
      : [];

    appendNotifications(nextNotifications);

    setBrowserWatchState(sessionId, current => ({
      ...current,
      lastActivityAt: new Date().toISOString(),
      lastError: null,
      lastStatus: 'open',
      lastStatusDetail: `${detailPrefix} processed=${payload.processed ?? 0} stored=${payload.stored ?? 0}`,
      running: true,
      subscriptions: [...subscriptions],
    }));
  }

  function maybeRunAutoHttpFallback(
    sessionId: number,
    subscriptions: string[],
    reason: 'fallback' | 'interval',
  ): void {
    const runtime = watchRuntimeRef.current;
    if (runtime?.transport !== 'auto') {
      return;
    }

    void runBrowserHttpRefresh(sessionId, subscriptions, reason, 'auto').catch(
      error => {
        if (browserSessionRef.current !== sessionId) {
          return;
        }

        const detail =
          error instanceof Error ? error.message : 'HTTP fallback failed';
        setBrowserWatchState(sessionId, current => ({
          ...current,
          lastActivityAt: new Date().toISOString(),
          lastError: detail,
          lastStatus: 'error',
          lastStatusDetail: detail,
          running: true,
          subscriptions: [...subscriptions],
        }));
      },
    );
  }

  function startBrowserHttpWatch(
    sessionId: number,
    subscriptions: string[],
    transport: 'auto' | 'http',
  ): void {
    clearBrowserHttpInterval();

    if (transport === 'http') {
      void runBrowserHttpRefresh(sessionId, subscriptions, 'start', 'http').catch(
        error => {
          if (browserSessionRef.current !== sessionId) {
            return;
          }

          const detail =
            error instanceof Error ? error.message : 'HTTP watch start failed';
          setBrowserWatchState(sessionId, current => ({
            ...current,
            lastActivityAt: new Date().toISOString(),
            lastError: detail,
            lastStatus: 'error',
            lastStatusDetail: detail,
            running: true,
            subscriptions: [...subscriptions],
          }));
        },
      );
    }

    browserHttpIntervalRef.current = window.setInterval(() => {
      if (transport === 'auto') {
        maybeRunAutoHttpFallback(sessionId, subscriptions, 'interval');
        return;
      }

      void runBrowserHttpRefresh(sessionId, subscriptions, 'interval', 'http').catch(
        error => {
          if (browserSessionRef.current !== sessionId) {
            return;
          }

          const detail =
            error instanceof Error ? error.message : 'HTTP polling failed';
          setBrowserWatchState(sessionId, current => ({
            ...current,
            lastActivityAt: new Date().toISOString(),
            lastError: detail,
            lastStatus: 'error',
            lastStatusDetail: detail,
            running: true,
            subscriptions: [...subscriptions],
          }));
        },
      );
    }, WATCH_INTERVAL_SEC * 1000);
  }

  function scheduleBrowserReconnect(
    sessionId: number,
    subscription: string,
    subscriptions: string[],
  ): void {
    if (browserSessionRef.current !== sessionId) {
      return;
    }

    clearBrowserTimerMap(browserReconnectTimersRef.current, subscription);

    browserReconnectTimersRef.current.set(
      subscription,
      window.setTimeout(() => {
        if (browserSessionRef.current !== sessionId) {
          return;
        }

        connectBrowserWatchSubscription(sessionId, subscription, subscriptions);
      }, BROWSER_WS_RECONNECT_DELAY_MS),
    );
  }

  function resetBrowserStaleTimer(
    sessionId: number,
    subscription: string,
    socket: WebSocket,
    subscriptions: string[],
  ): void {
    clearBrowserTimerMap(browserStaleTimersRef.current, subscription);

    browserStaleTimersRef.current.set(
      subscription,
      window.setTimeout(() => {
        if (browserSessionRef.current !== sessionId) {
          return;
        }

        const detail = `${getDexWatchSubscriptionLabel(subscription)} no messages for ${Math.round(
          BROWSER_WS_STALE_TIMEOUT_MS / 1000,
        )}s`;
        setBrowserWatchState(sessionId, current => ({
          ...current,
          lastActivityAt: new Date().toISOString(),
          lastError: detail,
          lastStatus: 'stale',
          lastStatusDetail: detail,
          running: true,
          subscriptions: [...subscriptions],
        }));
        maybeRunAutoHttpFallback(sessionId, subscriptions, 'fallback');

        if (
          socket.readyState === WebSocket.CONNECTING ||
          socket.readyState === WebSocket.OPEN
        ) {
          socket.close(1013, 'stale');
        }
      }, BROWSER_WS_STALE_TIMEOUT_MS),
    );
  }

  async function ingestBrowserPayload(
    sessionId: number,
    subscription: string,
    subscriptions: string[],
    payloadText: string,
  ): Promise<void> {
    const response = await fetch('/api/runtime/ingest', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        limit: WATCH_LIMIT,
        payloadText,
        subscription,
      }),
    });
    const payload = (await response.json().catch(() => ({}))) as RuntimeIngestResult;

    if (!response.ok) {
      throw new Error(
        typeof payload.message === 'string' && payload.message.trim()
          ? payload.message.trim()
          : `unexpected status ${response.status}`,
      );
    }

    if (browserSessionRef.current !== sessionId) {
      return;
    }

    const detail = `${getDexWatchSubscriptionLabel(subscription)} processed=${payload.processed ?? 0} stored=${payload.stored ?? 0}`;
    const nextNotifications = Array.isArray(payload.notifications)
      ? payload.notifications
      : [];

    appendNotifications(nextNotifications);

    setBrowserWatchState(sessionId, current => ({
      ...current,
      lastActivityAt: new Date().toISOString(),
      lastError: null,
      lastStatus: 'open',
      lastStatusDetail: detail,
      running: true,
      subscriptions: [...subscriptions],
    }));
  }

  function connectBrowserWatch(
    sessionId: number,
    subscriptions: string[],
  ): void {
    for (const subscription of subscriptions) {
      connectBrowserWatchSubscription(sessionId, subscription, subscriptions);
    }
  }

  function connectBrowserWatchSubscription(
    sessionId: number,
    subscription: string,
    subscriptions: string[],
  ): void {
    const endpoint = buildDexSubscriptionWsUrl(subscription, WATCH_LIMIT);

    const socket = new WebSocket(endpoint);
    browserSocketsRef.current.set(subscription, socket);

    setBrowserWatchState(sessionId, current => ({
      ...current,
      lastError: null,
      lastStatus: 'connecting',
      lastStatusDetail: `${getDexWatchSubscriptionLabel(subscription)} ${endpoint}`,
      running: true,
      subscriptions: [...subscriptions],
    }));

    clearBrowserTimerMap(browserConnectTimersRef.current, subscription);

    browserConnectTimersRef.current.set(
      subscription,
      window.setTimeout(() => {
        if (browserSessionRef.current !== sessionId) {
          return;
        }

        const detail = `connection timeout for ${subscription}`;
        setBrowserWatchState(sessionId, current => ({
          ...current,
          lastActivityAt: new Date().toISOString(),
          lastError: detail,
          lastStatus: 'error',
          lastStatusDetail: detail,
          running: true,
          subscriptions: [...subscriptions],
        }));
        maybeRunAutoHttpFallback(sessionId, subscriptions, 'fallback');

        if (
          socket.readyState === WebSocket.CONNECTING ||
          socket.readyState === WebSocket.OPEN
        ) {
          socket.close(1013, 'connect_timeout');
        }
      }, BROWSER_WS_CONNECT_TIMEOUT_MS),
    );

    socket.addEventListener('open', () => {
      if (browserSessionRef.current !== sessionId) {
        return;
      }

      clearBrowserTimerMap(browserConnectTimersRef.current, subscription);

      setBrowserWatchState(sessionId, current => ({
        ...current,
        lastActivityAt: new Date().toISOString(),
        lastError: null,
        lastStatus: 'open',
        lastStatusDetail: `${getDexWatchSubscriptionLabel(subscription)} connected`,
        running: true,
        subscriptions: [...subscriptions],
      }));
      resetBrowserStaleTimer(sessionId, subscription, socket, subscriptions);
    });

    socket.addEventListener('message', event => {
      if (browserSessionRef.current !== sessionId) {
        return;
      }

      resetBrowserStaleTimer(sessionId, subscription, socket, subscriptions);

      browserProcessingRef.current = browserProcessingRef.current
        .then(async () => {
          const payloadText = await readBrowserWsMessageText(event.data);
          if (!payloadText || browserSessionRef.current !== sessionId) {
            return;
          }

          setBrowserWatchState(sessionId, current => ({
            ...current,
            lastActivityAt: new Date().toISOString(),
            lastStatus: 'open',
            lastStatusDetail: `${getDexWatchSubscriptionLabel(subscription)} message received`,
            running: true,
            subscriptions: [...subscriptions],
          }));

          await ingestBrowserPayload(
            sessionId,
            subscription,
            subscriptions,
            payloadText,
          );
        })
        .catch(error => {
          if (browserSessionRef.current !== sessionId) {
            return;
          }

          const detail =
            error instanceof Error ? error.message : 'Unknown ingest error';
          setBrowserWatchState(sessionId, current => ({
            ...current,
            lastActivityAt: new Date().toISOString(),
            lastError: detail,
            lastStatus: 'error',
            lastStatusDetail: detail,
            running: true,
            subscriptions: [...subscriptions],
          }));
        });
    });

    socket.addEventListener('error', () => {
      if (browserSessionRef.current !== sessionId) {
        return;
      }

      const detail = `${getDexWatchSubscriptionLabel(subscription)} WebSocket transport error`;
      setBrowserWatchState(sessionId, current => ({
        ...current,
        lastActivityAt: new Date().toISOString(),
        lastError: detail,
        lastStatus: 'error',
        lastStatusDetail: detail,
        running: true,
        subscriptions: [...subscriptions],
      }));
      maybeRunAutoHttpFallback(sessionId, subscriptions, 'fallback');
    });

    socket.addEventListener('close', event => {
      if (browserSessionRef.current !== sessionId) {
        return;
      }

      clearBrowserWatchTimers(subscription);
      browserSocketsRef.current.delete(subscription);

      if (event.code === 1000) {
        return;
      }

      const detail = `${getDexWatchSubscriptionLabel(subscription)} code=${event.code}${
        event.reason ? ` reason=${event.reason}` : ''
      }`;
      setBrowserWatchState(sessionId, current => ({
        ...current,
        lastActivityAt: new Date().toISOString(),
        lastError: `socket closed for ${subscription} with code ${event.code}`,
        lastStatus: 'reconnecting',
        lastStatusDetail: detail,
        running: true,
        subscriptions: [...subscriptions],
      }));
      maybeRunAutoHttpFallback(sessionId, subscriptions, 'fallback');

      scheduleBrowserReconnect(sessionId, subscription, subscriptions);
    });
  }

  async function startWatch(): Promise<void> {
    setIsWatchMutating(true);

    try {
      if (selectedWatchSubscriptions.length === 0) {
        throw new Error('请至少选择一个订阅');
      }

      stopBrowserWatch();

      const sessionId = browserSessionRef.current + 1;
      browserSessionRef.current = sessionId;
      setWatchRuntime(
        createBrowserWatchState({
          lastStartedAt: new Date().toISOString(),
          lastStatus: 'starting',
          running: true,
          subscriptions: [...selectedWatchSubscriptions],
          transport: filters.watchTransport,
        }),
      );

      if (filters.watchTransport === 'http') {
        startBrowserHttpWatch(sessionId, selectedWatchSubscriptions, 'http');
        return;
      }

      if (filters.watchTransport === 'auto') {
        startBrowserHttpWatch(sessionId, selectedWatchSubscriptions, 'auto');
      }

      connectBrowserWatch(sessionId, selectedWatchSubscriptions);
    } catch (error) {
      setWatchRuntime(
        createBrowserWatchState({
          lastError: error instanceof Error ? error.message : 'watch_start_failed',
          lastStartedAt: new Date().toISOString(),
          lastStatus: 'error',
          lastStatusDetail:
            error instanceof Error ? error.message : 'watch_start_failed',
          running: false,
          subscriptions: [...selectedWatchSubscriptions],
          transport: filters.watchTransport,
        }),
      );
    } finally {
      setIsWatchMutating(false);
    }
  }

  async function stopWatch(): Promise<void> {
    setIsWatchMutating(true);

    try {
      stopBrowserWatch();
      setWatchRuntime(current =>
        createBrowserWatchState({
          lastActivityAt: current?.lastActivityAt ?? null,
          lastStartedAt: current?.lastStartedAt ?? null,
          lastStatus: 'stopped',
          running: false,
          subscriptions:
            current?.subscriptions.length
              ? [...current.subscriptions]
              : [...selectedWatchSubscriptions],
          transport: current?.transport ?? filters.watchTransport,
        }),
      );
    } catch (error) {
      setWatchRuntime(current =>
        current
          ? {
              ...current,
              lastError:
                error instanceof Error ? error.message : 'watch_stop_failed',
              lastStatus: 'error',
            }
          : null,
      );
    } finally {
      setIsWatchMutating(false);
    }
  }

  async function runDiagnostics(): Promise<void> {
    setIsDiagnosing(true);
    setDiagnosticsError('');

    try {
      const response = await fetch('/api/runtime/diagnostics', {
        method: 'POST',
        cache: 'no-store',
      });
      const payload = (await response.json().catch(() => ({}))) as Partial<
        RuntimeDiagnosticsResult
      > & {
        message?: string;
      };

      if (!response.ok) {
        throw new Error(
          typeof payload.message === 'string' && payload.message.trim()
            ? payload.message.trim()
            : `unexpected status ${response.status}`,
        );
      }

      setDiagnostics(payload as RuntimeDiagnosticsResult);
    } catch (error) {
      setDiagnosticsError(
        error instanceof Error ? error.message : 'Unknown diagnostics error',
      );
    } finally {
      setIsDiagnosing(false);
    }
  }

  function updateFilter<Key extends keyof DashboardFilters>(
    key: Key,
    value: DashboardFilters[Key],
  ): void {
    setFilters(current => ({ ...current, [key]: value }));
  }

  function resetFilters(): void {
    setFilters(initialFilters);
  }

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(0,162,142,0.14),transparent_28%),radial-gradient(circle_at_top_right,rgba(212,103,47,0.22),transparent_35%),linear-gradient(180deg,rgba(255,255,255,0.18),rgba(255,255,255,0))]" />

      <div className="relative mx-auto flex min-h-screen w-full max-w-[1440px] flex-col px-4 pb-10 pt-5 sm:px-6 lg:px-8">
        <header className="space-y-4 rounded-[34px] border border-white/50 bg-white/72 px-5 py-6 shadow-[0_24px_90px_rgba(53,42,33,0.08)] backdrop-blur lg:px-8">
          <Badge className="w-fit gap-2 rounded-full px-3 py-1.5 text-[10px]">
            <BellRing className="size-3" />
            Signal Trade Notifications
          </Badge>
          <div className="space-y-3">
            <h1 className="text-3xl font-semibold tracking-[-0.05em] text-balance text-foreground sm:text-4xl">
              只保留筛选和通知列表
            </h1>
            <p className="max-w-2xl text-sm leading-7 text-muted-foreground sm:text-base">
              左侧设置筛选条件，右侧直接查看当前页面会话里的通知。刷新页面后，通知和筛选都会回到初始状态。
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              className="rounded-full"
              disabled={isRefreshing}
              onClick={() => {
                void syncNotifications();
              }}
            >
              {isRefreshing ? (
                <LoaderCircle className="size-4 animate-spin" />
              ) : (
                <RefreshCw className="size-4" />
              )}
              同步通知
            </Button>
            <SessionChip />
            <RefreshChip refreshState={refreshState} />
            <WatchChip watchRuntime={watchRuntime} />
          </div>
          {refreshSummary ? (
            <p className="text-xs leading-6 text-muted-foreground">{refreshSummary}</p>
          ) : null}
        </header>

        <div className="mt-6 grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
          <aside className="space-y-6 xl:sticky xl:top-6 xl:self-start">
            <Card className="overflow-hidden">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-xl">
                  <Filter className="size-5 text-[color:var(--color-accent)]" />
                  Dashboard Filters
                </CardTitle>
                <CardDescription>
                  这些筛选只影响当前页面展示，不会写入浏览器缓存，也不会写到 Node 端。
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <FieldGroup label="快速搜索">
                  <div className="relative">
                    <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      className="pl-10"
                      placeholder="代币、来源、Twitter 用户名"
                      value={filters.search}
                      onChange={event => updateFilter('search', event.target.value)}
                    />
                  </div>
                </FieldGroup>

                <FieldGroup label="观察名单关键词">
                  <Textarea
                    placeholder="支持逗号或换行，例如：ansem, base, hype"
                    value={filters.watchTerms}
                    onChange={event => updateFilter('watchTerms', event.target.value)}
                  />
                </FieldGroup>

                <FieldGroup label="监听模式">
                  <SelectField
                    options={['auto', 'ws', 'http']}
                    value={filters.watchTransport}
                    onChange={value =>
                      updateFilter('watchTransport', value as DashboardFilters['watchTransport'])
                    }
                  />
                </FieldGroup>

                <FieldGroup label="WS 订阅">
                  <SubscriptionMultiSelect
                    selectedSubscriptions={filters.watchSubscriptions}
                    onToggle={subscription =>
                      updateFilter(
                        'watchSubscriptions',
                        toggleWatchSubscription(
                          filters.watchSubscriptions,
                          subscription,
                        ),
                      )
                    }
                  />
                  <p className="text-xs leading-6 text-muted-foreground">
                    只有选中的 DexScreener feed 会被订阅；未选中的不会连接。
                  </p>
                </FieldGroup>

                <FieldGroup label="KOL 名单">
                  <Textarea
                    placeholder="当前停用 XXYY，KOL 筛选暂不可用"
                    value={filters.kolNames}
                    onChange={event => updateFilter('kolNames', event.target.value)}
                  />
                </FieldGroup>

                <FieldGroup label="关注地址">
                  <Textarea
                    placeholder="当前停用 XXYY，关注地址筛选暂不可用"
                    value={filters.followAddresses}
                    onChange={event =>
                      updateFilter('followAddresses', event.target.value)
                    }
                  />
                </FieldGroup>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-1">
                  <FieldGroup label="链路">
                    <SelectField
                      options={['all', ...chainOptions]}
                      value={filters.chain}
                      onChange={value => updateFilter('chain', value)}
                    />
                  </FieldGroup>
                  <FieldGroup label="来源">
                    <SelectField
                      options={['all', ...sourceOptions]}
                      value={filters.source}
                      onChange={value => updateFilter('source', value)}
                    />
                  </FieldGroup>
                  <FieldGroup label="最少持币人数">
                    <Input
                      inputMode="numeric"
                      placeholder="100"
                      value={filters.minHolders}
                      onChange={event => updateFilter('minHolders', event.target.value)}
                    />
                  </FieldGroup>
                  <FieldGroup label="最多持币人数">
                    <Input
                      inputMode="numeric"
                      placeholder="5000"
                      value={filters.maxHolders}
                      onChange={event => updateFilter('maxHolders', event.target.value)}
                    />
                  </FieldGroup>
                  <FieldGroup label="最高市值">
                    <Input
                      inputMode="numeric"
                      placeholder="3000000"
                      value={filters.maxMarketCap}
                      onChange={event => updateFilter('maxMarketCap', event.target.value)}
                    />
                  </FieldGroup>
                  <FieldGroup label="最少社区人数">
                    <Input
                      inputMode="numeric"
                      placeholder="5000"
                      value={filters.minCommunityCount}
                      onChange={event =>
                        updateFilter('minCommunityCount', event.target.value)
                      }
                    />
                  </FieldGroup>
                </div>

                <button
                  type="button"
                  className={cn(
                    'flex w-full items-center justify-between rounded-3xl border px-4 py-3 text-left transition-colors',
                    filters.paidOnly
                      ? 'border-[color:var(--color-accent)] bg-[color:var(--color-accent)]/8'
                      : 'border-border bg-[color:var(--color-panel-soft)]',
                  )}
                  onClick={() => updateFilter('paidOnly', !filters.paidOnly)}
                >
                  <div>
                    <p className="text-sm font-semibold text-foreground">
                      仅看 Paid Dex 通知
                    </p>
                    <p className="text-xs text-muted-foreground">
                      对应 `dexscreener.paid = true`
                    </p>
                  </div>
                  <Badge variant={filters.paidOnly ? 'success' : 'secondary'}>
                    {filters.paidOnly ? 'ON' : 'OFF'}
                  </Badge>
                </button>

                <div className="flex flex-wrap gap-3">
                  <Button className="w-full rounded-full" variant="outline" onClick={resetFilters}>
                    重置
                  </Button>
                </div>

                <div className="flex flex-wrap gap-3">
                  <Button
                    className="flex-1 rounded-full"
                    disabled={isWatchMutating}
                    variant="secondary"
                    onClick={() => {
                      void startWatch();
                    }}
                  >
                    {watchRuntime?.running ? '重启监听' : '启动监听'}
                  </Button>
                  <Button
                    className="rounded-full"
                    disabled={isWatchMutating || !watchRuntime?.running}
                    variant="outline"
                    onClick={() => {
                      void stopWatch();
                    }}
                  >
                    停止监听
                  </Button>
                </div>
                <Button
                  className="w-full rounded-full"
                  disabled={isDiagnosing}
                  variant="outline"
                  onClick={() => {
                    void runDiagnostics();
                  }}
                >
                  {isDiagnosing ? (
                    <LoaderCircle className="size-4 animate-spin" />
                  ) : (
                    <Target className="size-4" />
                  )}
                  运行网络诊断
                </Button>
                <p className="text-xs leading-6 text-muted-foreground">
                  当前页面直接控制 `auto / ws / http`。`ws` 由浏览器直连，`http`
                  由浏览器定时请求刷新接口；通知只保留在当前页面内存，不写浏览器缓存，也不写 Node 存储。
                </p>
                <p className="text-xs leading-6 text-muted-foreground">
                  当前已停用 XXYY 富化，通知卡片优先直接展示 DexScreener feed 自带字段。
                </p>
                <p className="text-xs leading-6 text-muted-foreground">
                  `KOL 名单` 与 `关注地址` 仍保留在表单里，但当前不会参与过滤。
                </p>
                <WatchStatusPanel watchRuntime={watchRuntime} />
                <DiagnosticsPanel
                  diagnostics={diagnostics}
                  diagnosticsError={diagnosticsError}
                />
              </CardContent>
            </Card>
          </aside>

          <section className="overflow-hidden rounded-[32px] border border-white/50 bg-white/72 shadow-[0_24px_90px_rgba(53,42,33,0.08)] backdrop-blur">
            <div className="border-b border-border/70 px-5 py-5 sm:px-6">
              <div className="flex items-center gap-2 text-xl font-semibold text-foreground">
                <Layers className="size-5 text-[color:var(--color-accent)]" />
                Notification Stream
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                当前页面会话累计记录 {notifications.length} 条通知，筛选后显示{' '}
                {filteredNotifications.length} 条。
              </p>
            </div>
            <div className="p-0">
                {filteredNotifications.length > 0 ? (
                  <ol className="divide-y divide-border">
                    {filteredNotifications.map(record => (
                      <NotificationListItem
                        key={record.id}
                        currentTimeMs={relativeNow}
                        record={record}
                      />
                    ))}
                  </ol>
                ) : (
                  <EmptyState />
                )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function SessionChip(): JSX.Element {
  return (
    <Badge variant="secondary" className="px-3 py-1.5 normal-case tracking-normal">
      仅当前页面会话
    </Badge>
  );
}

function RefreshChip({
  refreshState,
}: {
  refreshState: RefreshState;
}): JSX.Element | null {
  if (refreshState === 'idle') {
    return null;
  }
  if (refreshState === 'syncing') {
    return (
      <Badge variant="secondary" className="gap-2 px-3 py-1.5 normal-case tracking-normal">
        <LoaderCircle className="size-3 animate-spin" />
        正在同步信号
      </Badge>
    );
  }
  if (refreshState === 'synced') {
    return (
      <Badge variant="success" className="px-3 py-1.5 normal-case tracking-normal">
        已更新当前会话通知
      </Badge>
    );
  }
  return (
    <Badge className="px-3 py-1.5 normal-case tracking-normal" variant="outline">
      同步失败
    </Badge>
  );
}

function WatchChip({
  watchRuntime,
}: {
  watchRuntime: WatchRuntimeState | null;
}): JSX.Element {
  if (!watchRuntime) {
    return (
      <Badge variant="secondary" className="px-3 py-1.5 normal-case tracking-normal">
        监听状态未知
      </Badge>
    );
  }

  if (hasWatchConnectionIssue(watchRuntime)) {
    return (
      <Badge className="px-3 py-1.5 normal-case tracking-normal" variant="outline">
        连接异常 {watchRuntime.transport}
      </Badge>
    );
  }

  if (watchRuntime.running) {
    return (
      <Badge
        variant={
          watchRuntime.lastStatus === 'connecting' ||
          watchRuntime.lastStatus === 'reconnecting'
            ? 'secondary'
            : 'success'
        }
        className="px-3 py-1.5 normal-case tracking-normal"
      >
        {watchRuntime.lastStatus === 'connecting' ||
        watchRuntime.lastStatus === 'reconnecting'
          ? '连接中'
          : '监听中'}{' '}
        {watchRuntime.transport}
      </Badge>
    );
  }

  return (
    <Badge variant="secondary" className="px-3 py-1.5 normal-case tracking-normal">
      监听未启动
    </Badge>
  );
}

function WatchStatusPanel({
  watchRuntime,
}: {
  watchRuntime: WatchRuntimeState | null;
}): JSX.Element | null {
  if (!watchRuntime) {
    return null;
  }

  const detail = watchRuntime.lastError ?? watchRuntime.lastStatusDetail;
  const toneClass =
    hasWatchConnectionIssue(watchRuntime)
      ? 'border-red-200/80 bg-red-50/80 text-red-700'
      : 'border-border bg-[color:var(--color-panel-soft)] text-muted-foreground';

  return (
    <div className={cn('rounded-3xl border px-4 py-3 text-xs leading-6', toneClass)}>
      <p>
        watcher 状态：{formatWatchStatus(watchRuntime)}，模式 {watchRuntime.transport}
      </p>
      {watchRuntime.subscriptions.length > 0 ? (
        <p>订阅：{formatWatchSubscriptions(watchRuntime.subscriptions)}</p>
      ) : null}
      {watchRuntime.lastActivityAt ? (
        <p>最后活动：{formatAbsoluteTime(watchRuntime.lastActivityAt)}</p>
      ) : null}
      {detail ? <p className="break-all">详情：{detail}</p> : null}
    </div>
  );
}

function DiagnosticsPanel({
  diagnostics,
  diagnosticsError,
}: {
  diagnostics: RuntimeDiagnosticsResult | null;
  diagnosticsError: string;
}): JSX.Element | null {
  if (!diagnostics && !diagnosticsError) {
    return null;
  }

  return (
    <div className="rounded-3xl border border-border bg-[color:var(--color-panel-soft)] px-4 py-3 text-xs leading-6 text-muted-foreground">
      <p className="font-semibold text-foreground">网络诊断</p>
      {diagnosticsError ? (
        <p className="mt-2 break-all text-red-700">执行失败：{diagnosticsError}</p>
      ) : null}
      {diagnostics ? (
        <>
          <p className="mt-2">检查时间：{formatAbsoluteTime(diagnostics.checkedAt)}</p>
          <p>通知存储：{formatNotificationStore(diagnostics.notificationsStore)}</p>
          <p>HTTP：{formatNetworkCheck(diagnostics.httpCheck)}</p>
          <p>WS：{formatNetworkCheck(diagnostics.wsCheck)}</p>
          {Object.keys(diagnostics.proxyEnv).length > 0 ? (
            <div className="mt-2 space-y-1">
              <p className="text-foreground">代理环境变量：</p>
              {Object.entries(diagnostics.proxyEnv).map(([key, value]) => (
                <p key={key} className="break-all font-mono text-[11px]">
                  {key}={value}
                </p>
              ))}
            </div>
          ) : (
            <p className="mt-2">代理环境变量：未检测到</p>
          )}
        </>
      ) : null}
    </div>
  );
}

function NotificationListItem({
  currentTimeMs,
  record,
}: {
  currentTimeMs: number;
  record: NotificationRecord;
}): JSX.Element {
  const sourceKey = `${record.event.source}.${record.event.subtype}`;
  const displayAddress =
    record.context.token?.address || record.event.token.address || null;
  const displaySymbol =
    record.context.token?.symbol ||
    record.event.token.symbol ||
    (displayAddress ? truncateMiddle(displayAddress, 6, 4).toUpperCase() : 'UNKNOWN');
  const displayName =
    record.context.token?.name ||
    record.event.token.name ||
    record.context.token?.address ||
    record.event.token.address ||
    'unnamed token';
  const displayText =
    record.context.dexscreener?.description ||
    record.context.dexscreener?.header ||
    record.event.text ||
    record.message;
  const rawAmount = asOptionalNumber(record.event.metrics?.amount);
  const rawTotalAmount = asOptionalNumber(record.event.metrics?.totalAmount);
  const rawActiveBoosts = asOptionalNumber(record.event.metrics?.activeBoosts);
  const twitterProfileUrl = record.context.twitter?.profile_url ?? null;

  return (
    <li className="px-5 py-4 transition-colors hover:bg-white/50 sm:px-6">
      <div className="flex flex-col gap-3">
        <div className="flex items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-3">
            <TokenAvatar
              imageUrl={record.summary.imageUrl}
              symbol={displaySymbol}
            />
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-base font-semibold tracking-[-0.03em] text-foreground">
                  {displaySymbol}
                </p>
                <Badge variant={record.summary.paid ? 'success' : 'secondary'}>
                  {record.summary.paid ? 'paid' : 'organic'}
                </Badge>
                <span className="rounded-full bg-[color:var(--color-panel-soft)] px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                  {record.event.chain || 'n/a'}
                </span>
              </div>
              <p className="mt-1 truncate text-sm text-foreground/80">{displayName}</p>
              {displayAddress ? (
                <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                  {truncateMiddle(displayAddress, 8, 6)}
                </p>
              ) : null}
            </div>
          </div>
          <div className="shrink-0 text-right">
            <p className="font-mono text-[11px] text-muted-foreground">
              {formatRelativeTime(record.notifiedAt, currentTimeMs)}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {formatAbsoluteTime(record.notifiedAt)}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <InfoPill icon={Activity} label={sourceKey} />
          {record.event.author?.display_name ? (
            <InfoPill icon={Target} label={record.event.author.display_name} />
          ) : null}
          {rawActiveBoosts !== null ? (
            <InfoPill icon={Layers} label={`active boosts ${formatPlainMetric(rawActiveBoosts)}`} />
          ) : null}
          {record.channels.length > 0 ? (
            <InfoPill icon={BellRing} label={record.channels.join(', ')} />
          ) : null}
        </div>

        <div className="grid gap-2 text-sm sm:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
          <p className="min-w-0 truncate text-muted-foreground">{displayText}</p>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-right sm:grid-cols-3">
            <MetricPair label="市值" value={formatUsd(record.summary.marketCap)} />
            <MetricPair
              label="流动性"
              value={formatUsd(record.summary.liquidityUsd)}
            />
            <MetricPair
              label="价格"
              value={formatPriceUsd(record.summary.priceUsd)}
            />
            <MetricPair
              label="FDV"
              value={formatUsd(record.context.dexscreener?.fdv ?? null)}
            />
            <MetricPair
              label="单次金额"
              value={formatLooseNumber(rawAmount)}
            />
            <MetricPair
              label="累计金额"
              value={formatLooseNumber(rawTotalAmount)}
            />
          </dl>
        </div>

        <p className="text-[11px] text-muted-foreground">
          当前卡片直接展示 DexScreener feed 字段；不再请求 XXYY 富化。
        </p>

        <div className="flex flex-wrap gap-2">
          {record.summary.twitterUsername && twitterProfileUrl ? (
            <a
              className="inline-flex items-center gap-1 rounded-full border border-border px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-[color:var(--color-panel-soft)]"
              href={twitterProfileUrl}
              rel="noreferrer"
              target="_blank"
            >
              @{record.summary.twitterUsername}
              <ArrowUpRight className="size-3" />
            </a>
          ) : null}
          {record.summary.dexscreenerUrl ? (
            <a
              className="inline-flex items-center gap-1 rounded-full border border-border px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-[color:var(--color-panel-soft)]"
              href={record.summary.dexscreenerUrl}
              rel="noreferrer"
              target="_blank"
            >
              Dex
              <ArrowUpRight className="size-3" />
            </a>
          ) : null}
          {record.summary.telegramUrl ? (
            <a
              className="inline-flex items-center gap-1 rounded-full border border-border px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-[color:var(--color-panel-soft)]"
              href={record.summary.telegramUrl}
              rel="noreferrer"
              target="_blank"
            >
              Telegram
              <ArrowUpRight className="size-3" />
            </a>
          ) : null}
        </div>
      </div>
    </li>
  );
}

function TokenAvatar({
  imageUrl,
  symbol,
}: {
  imageUrl: string | null;
  symbol: string;
}): JSX.Element {
  const [imageFailed, setImageFailed] = useState(false);
  const label = symbol.trim().slice(0, 2).toUpperCase() || 'TK';

  if (imageUrl && !imageFailed) {
    return (
      <img
        alt={symbol}
        className="size-12 rounded-2xl border border-border/80 bg-[color:var(--color-panel-soft)] object-cover"
        height={48}
        loading="lazy"
        src={imageUrl}
        width={48}
        onError={() => {
          setImageFailed(true);
        }}
      />
    );
  }

  return (
    <div className="flex size-12 items-center justify-center rounded-2xl border border-border/80 bg-[color:var(--color-panel-soft)] text-sm font-semibold text-foreground">
      {label}
    </div>
  );
}

function EmptyState(): JSX.Element {
  return (
    <div className="px-6 py-10">
      <div className="flex min-h-[280px] flex-col items-center justify-center rounded-[32px] border border-dashed border-border bg-[color:var(--color-panel-soft)] px-6 py-10 text-center">
        <div className="rounded-full bg-[color:var(--color-accent)]/10 p-4 text-[color:var(--color-accent)]">
          <BellRing className="size-8" />
        </div>
        <h3 className="mt-5 text-2xl font-semibold tracking-[-0.04em] text-foreground">
          当前没有符合筛选条件的通知
        </h3>
        <p className="mt-3 max-w-md text-sm leading-6 text-muted-foreground">
          你可以降低前端筛选阈值，点击上方“同步通知”，或者直接启动 `ws / http`
          监听，把新通知写入当前页面会话。
        </p>
      </div>
    </div>
  );
}

function MetricPair({
  label,
  value,
}: {
  label: string;
  value: string;
}): JSX.Element {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-1 font-semibold text-foreground">{value}</dd>
    </div>
  );
}

function InfoPill({
  icon: Icon,
  label,
}: {
  icon: LucideIcon;
  label: string;
}): JSX.Element {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-[color:var(--color-panel-soft)] px-3 py-1.5 text-[11px] font-medium text-muted-foreground">
      <Icon className="size-3.5" />
      {label}
    </span>
  );
}

function FieldGroup({
  children,
  label,
}: {
  children: ReactNode;
  label: string;
}): JSX.Element {
  return (
    <div className="space-y-2.5">
      <Label>{label}</Label>
      {children}
    </div>
  );
}

function SelectField({
  onChange,
  options,
  value,
}: {
  onChange: (value: string) => void;
  options: string[];
  value: string;
}): JSX.Element {
  return (
    <div className="relative">
      <select
        className="h-11 w-full appearance-none rounded-2xl border border-border bg-[color:var(--color-panel-soft)] px-4 py-2 text-sm text-foreground outline-none transition-colors focus:border-[color:var(--color-accent)] focus:bg-white"
        onChange={event => onChange(event.target.value)}
        value={value}
      >
        {options.map(option => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
      <Target className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
    </div>
  );
}

function SubscriptionMultiSelect({
  onToggle,
  selectedSubscriptions,
}: {
  onToggle: (subscription: string) => void;
  selectedSubscriptions: string[];
}): JSX.Element {
  return (
    <div className="grid gap-2">
      {DEX_WATCH_SUBSCRIPTION_OPTIONS.map(option => {
        const selected = selectedSubscriptions.includes(option.id);

        return (
          <button
            key={option.id}
            type="button"
            className={cn(
              'flex w-full items-center justify-between rounded-2xl border px-4 py-3 text-left transition-colors',
              selected
                ? 'border-[color:var(--color-accent)] bg-[color:var(--color-accent)]/8'
                : 'border-border bg-[color:var(--color-panel-soft)]',
            )}
            onClick={() => onToggle(option.id)}
          >
            <span className="text-sm text-foreground">{option.label}</span>
            <Badge variant={selected ? 'success' : 'secondary'}>
              {selected ? 'ON' : 'OFF'}
            </Badge>
          </button>
        );
      })}
    </div>
  );
}

function uniqueValues(values: string[]): string[] {
  return Array.from(
    new Set(values.map(item => item.trim()).filter(Boolean)),
  ).sort((left, right) => left.localeCompare(right));
}

function parseListFilter(value: string): string[] {
  return value
    .split(/[\n,]/)
    .map(item => item.trim().toLowerCase())
    .filter(Boolean);
}

function getSelectedWatchSubscriptions(value: string[]): string[] {
  return DEX_WATCH_SUBSCRIPTION_OPTIONS
    .map(option => option.id)
    .filter(option => value.includes(option));
}

function toggleWatchSubscription(
  selectedSubscriptions: string[],
  subscription: string,
): string[] {
  const nextSelected = selectedSubscriptions.includes(subscription)
    ? selectedSubscriptions.filter(item => item !== subscription)
    : [...selectedSubscriptions, subscription];

  return DEX_WATCH_SUBSCRIPTION_OPTIONS
    .map(option => option.id)
    .filter(option => nextSelected.includes(option));
}

function mergeNotifications(
  current: NotificationRecord[],
  incoming: NotificationRecord[],
): NotificationRecord[] {
  const merged = new Map<string, NotificationRecord>();

  for (const record of [...incoming, ...current]) {
    const existing = merged.get(record.id);
    if (!existing) {
      merged.set(record.id, record);
      continue;
    }

    if (
      new Date(record.notifiedAt).getTime() >
      new Date(existing.notifiedAt).getTime()
    ) {
      merged.set(record.id, record);
    }
  }

  return Array.from(merged.values())
    .sort(
      (left, right) =>
        new Date(right.notifiedAt).getTime() - new Date(left.notifiedAt).getTime(),
    )
    .slice(0, MAX_SESSION_NOTIFICATIONS);
}

function clearBrowserTimerMap(
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

function parseNumericFilter(value: string): number | null {
  if (!value.trim()) {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatUsd(value: number | null): string {
  if (value === null) {
    return 'N/A';
  }
  return `$${formatCompactNumber(value)}`;
}

function formatOptionalNumber(value: number | null): string {
  if (value === null) {
    return 'N/A';
  }
  return formatCompactNumber(value);
}

function formatLooseNumber(value: number | null): string {
  if (value === null) {
    return 'N/A';
  }
  return formatPlainMetric(value);
}

function formatPriceUsd(value: number | null): string {
  if (value === null) {
    return 'N/A';
  }

  if (value >= 1) {
    return `$${formatPlainNumber(Number(value.toFixed(4)))}`;
  }

  return `$${trimTrailingZeros(value.toFixed(8))}`;
}

function formatPlainMetric(value: number): string {
  if (Number.isInteger(value)) {
    return formatPlainNumber(value);
  }

  return trimTrailingZeros(value.toFixed(Math.abs(value) >= 1 ? 4 : 8));
}

function formatRelativeTime(value: string, currentTimeMs: number): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return 'unknown';
  }

  const diffMs = date.getTime() - currentTimeMs;
  const diffMinutes = Math.round(diffMs / 60_000);
  if (Math.abs(diffMinutes) < 60) {
    return `${Math.abs(diffMinutes)}m ${diffMinutes <= 0 ? 'ago' : 'later'}`;
  }
  const diffHours = Math.round(diffMinutes / 60);
  if (Math.abs(diffHours) < 24) {
    return `${Math.abs(diffHours)}h ${diffHours <= 0 ? 'ago' : 'later'}`;
  }
  const diffDays = Math.round(diffHours / 24);
  return `${Math.abs(diffDays)}d ${diffDays <= 0 ? 'ago' : 'later'}`;
}

function formatWatchStatus(watchRuntime: WatchRuntimeState): string {
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

function formatWatchSubscriptions(subscriptions: string[]): string {
  return subscriptions.map(getDexWatchSubscriptionLabel).join(', ');
}

function hasWatchConnectionIssue(watchRuntime: WatchRuntimeState): boolean {
  if (!watchRuntime.running) {
    return watchRuntime.lastStatus === 'error' || watchRuntime.lastStatus === 'stale';
  }

  return Boolean(watchRuntime.lastError) || watchRuntime.lastStatus === 'error' || watchRuntime.lastStatus === 'stale';
}

function formatNotificationStore(
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

function formatNetworkCheck(
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

function formatDurationMs(value: number): string {
  if (!Number.isFinite(value) || value < 0) {
    return 'n/a';
  }

  if (value < 1000) {
    return `${value}ms`;
  }

  return `${(value / 1000).toFixed(1)}s`;
}

function formatAbsoluteTime(value: string): string {
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

function createBrowserWatchState(
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

function buildDexSubscriptionWsUrl(subscription: string, limit: number): string {
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

async function readBrowserWsMessageText(data: unknown): Promise<string | null> {
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

function formatCompactNumber(value: number): string {
  const abs = Math.abs(value);

  if (abs >= 1_000_000_000) {
    return `${formatCompactUnit(value / 1_000_000_000)}B`;
  }
  if (abs >= 1_000_000) {
    return `${formatCompactUnit(value / 1_000_000)}M`;
  }
  if (abs >= 1_000) {
    return `${formatCompactUnit(value / 1_000)}K`;
  }

  return formatPlainNumber(value);
}

function formatCompactUnit(value: number): string {
  const abs = Math.abs(value);
  const decimals = abs < 100 ? 1 : 0;
  return trimTrailingZeros(value.toFixed(decimals));
}

function formatPlainNumber(value: number): string {
  const normalized = Number.isInteger(value)
    ? value.toString()
    : trimTrailingZeros(value.toFixed(1));

  const [integerPart, fractionPart] = normalized.split('.');
  const sign = integerPart.startsWith('-') ? '-' : '';
  const unsignedInteger = sign ? integerPart.slice(1) : integerPart;
  const groupedInteger = unsignedInteger.replace(/\B(?=(\d{3})+(?!\d))/g, ',');

  return fractionPart
    ? `${sign}${groupedInteger}.${fractionPart}`
    : `${sign}${groupedInteger}`;
}

function trimTrailingZeros(value: string): string {
  return value.replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1');
}

function padNumber(value: number): string {
  return value.toString().padStart(2, '0');
}

function truncateMiddle(
  value: string,
  start = 6,
  end = 4,
): string {
  if (value.length <= start + end + 3) {
    return value;
  }

  return `${value.slice(0, start)}...${value.slice(-end)}`;
}

function asOptionalNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  return null;
}

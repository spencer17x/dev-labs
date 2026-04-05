'use client';

import { useEffect, useRef, useState } from 'react';
import {
  splitDisplayReadyNotifications,
  streamBackfilledNotifications,
  shouldBackfillNotificationDetails,
} from '@/lib/browser-notification-details';
import { refreshDexNotificationsInBrowser } from '@/lib/browser-refresh';
import { fetchDexTokenDetailsByChain } from '@/lib/dexscreener-token-details';
import { getDexWatchSubscriptionLabel } from '@/lib/dexscreener-subscriptions';
import { ingestDexPayloadText } from '@/lib/ingest/ingest-dex-payload';
import type { NotificationRecord, WatchRuntimeState } from '@/lib/types';
import {
  BROWSER_WS_CONNECT_TIMEOUT_MS,
  BROWSER_WS_RECONNECT_DELAY_MS,
  BROWSER_WS_STALE_TIMEOUT_MS,
  buildDexSubscriptionWsUrl,
  clearBrowserTimerMap,
  createBrowserWatchState,
  readBrowserWsMessageText,
  WATCH_INTERVAL_SEC,
  WATCH_LIMIT,
} from '@/lib/watch-utils';

interface UseBrowserWatchOptions {
  onNotifications: (records: NotificationRecord[]) => void;
}

interface UseBrowserWatchResult {
  watchRuntime: WatchRuntimeState | null;
  watchRuntimeRef: React.RefObject<WatchRuntimeState | null>;
  isWatchMutating: boolean;
  startWatch: (subscriptions: string[], transport: 'auto' | 'http' | 'ws') => Promise<void>;
  stopWatch: (subscriptions: string[], transport?: 'auto' | 'http' | 'ws') => Promise<void>;
}

const BROWSER_WS_CLOSE_CODE_STALE = 4001;
const BROWSER_WS_CLOSE_CODE_CONNECT_TIMEOUT = 4002;

export function useBrowserWatch({ onNotifications }: UseBrowserWatchOptions): UseBrowserWatchResult {
  const [watchRuntime, setWatchRuntime] = useState<WatchRuntimeState | null>(null);
  const [isWatchMutating, setIsWatchMutating] = useState(false);

  const browserConnectTimersRef = useRef(new Map<string, number>());
  const browserDetailBackfillRef = useRef(new Set<string>());
  const browserReconnectTimersRef = useRef(new Map<string, number>());
  const browserStaleTimersRef = useRef(new Map<string, number>());
  const browserHttpIntervalRef = useRef<number | null>(null);
  const browserProcessingRef = useRef<Promise<void>>(Promise.resolve());
  const browserSessionRef = useRef(0);
  const browserSocketsRef = useRef(new Map<string, WebSocket>());
  const watchRuntimeRef = useRef<WatchRuntimeState | null>(null);

  useEffect(() => {
    watchRuntimeRef.current = watchRuntime;
  }, [watchRuntime]);

  useEffect(() => {
    return () => {
      teardownBrowserWatch();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
    browserDetailBackfillRef.current.clear();
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

    const payload = await refreshDexNotificationsInBrowser({
      limit: WATCH_LIMIT,
      subscriptions,
    });

    if (browserSessionRef.current !== sessionId) {
      return;
    }

    const nextNotifications = Array.isArray(payload.notifications)
      ? payload.notifications
      : [];

    const { deferredNotifications, immediateNotifications } =
      splitDisplayReadyNotifications(nextNotifications);

    if (immediateNotifications.length > 0) {
      onNotifications(immediateNotifications);
    }
    void backfillBrowserNotificationDetails(sessionId, deferredNotifications);

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
          socket.close(BROWSER_WS_CLOSE_CODE_STALE, 'stale');
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
    const payload = await ingestDexPayloadText({
      fetchDetailsByChain: fetchDexTokenDetailsByChain,
      payloadText,
      subscription,
    });

    if (browserSessionRef.current !== sessionId) {
      return;
    }

    const detail = `${getDexWatchSubscriptionLabel(subscription)} processed=${payload.processed ?? 0} stored=${payload.stored ?? 0}`;
    const nextNotifications = Array.isArray(payload.notifications)
      ? payload.notifications
      : [];

    const { deferredNotifications, immediateNotifications } =
      splitDisplayReadyNotifications(nextNotifications);

    if (immediateNotifications.length > 0) {
      onNotifications(immediateNotifications);
    }
    void backfillBrowserNotificationDetails(sessionId, deferredNotifications);

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

  async function backfillBrowserNotificationDetails(
    sessionId: number,
    notifications: NotificationRecord[],
  ): Promise<void> {
    const candidates = notifications.filter(record => {
      if (!shouldBackfillNotificationDetails(record)) {
        return false;
      }

      if (browserDetailBackfillRef.current.has(record.id)) {
        return false;
      }

      browserDetailBackfillRef.current.add(record.id);
      return true;
    });
    if (candidates.length === 0) {
      return;
    }

    try {
      await streamBackfilledNotifications(candidates, {
        fetchDetailsByChain: fetchDexTokenDetailsByChain,
        onBatch: nextNotifications => {
          if (browserSessionRef.current !== sessionId) {
            return;
          }

          if (nextNotifications.length > 0) {
            onNotifications(nextNotifications);
          }
        },
      });
    } catch {
      // Background detail hydration is best-effort. Keep the immediate WS notification.
    } finally {
      for (const record of candidates) {
        browserDetailBackfillRef.current.delete(record.id);
      }
    }
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
    const endpoint = buildDexSubscriptionWsUrl(subscription);

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
          socket.close(BROWSER_WS_CLOSE_CODE_CONNECT_TIMEOUT, 'connect_timeout');
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

  async function startWatch(subscriptions: string[], transport: 'auto' | 'http' | 'ws'): Promise<void> {
    setIsWatchMutating(true);

    try {
      if (subscriptions.length === 0) {
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
          subscriptions: [...subscriptions],
          transport,
        }),
      );

      if (transport === 'http') {
        startBrowserHttpWatch(sessionId, subscriptions, 'http');
        return;
      }

      if (transport === 'auto') {
        startBrowserHttpWatch(sessionId, subscriptions, 'auto');
      }

      connectBrowserWatch(sessionId, subscriptions);
    } catch (error) {
      setWatchRuntime(
        createBrowserWatchState({
          lastError: error instanceof Error ? error.message : 'watch_start_failed',
          lastStartedAt: new Date().toISOString(),
          lastStatus: 'error',
          lastStatusDetail:
            error instanceof Error ? error.message : 'watch_start_failed',
          running: false,
          subscriptions: [...subscriptions],
          transport,
        }),
      );
    } finally {
      setIsWatchMutating(false);
    }
  }

  async function stopWatch(subscriptions: string[], transport?: 'auto' | 'http' | 'ws'): Promise<void> {
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
              : [...subscriptions],
          transport: current?.transport ?? transport ?? 'auto',
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

  return { watchRuntime, watchRuntimeRef, isWatchMutating, startWatch, stopWatch };
}

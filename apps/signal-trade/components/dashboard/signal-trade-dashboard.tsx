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
  Check,
  Copy,
  Filter,
  Layers,
  LoaderCircle,
  RefreshCw,
  Search,
  SlidersHorizontal,
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
import { Dialog } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  DEFAULT_DEX_WATCH_SUBSCRIPTIONS,
  DEX_WATCH_SUBSCRIPTION_OPTIONS,
  getDexWatchSubscriptionLabel,
} from '@/lib/dexscreener-subscriptions';
import {
  applyStrategyPreset,
  isStrategyPresetEnabled,
  STRATEGY_PRESET_OPTIONS,
} from '@/lib/strategy-presets';
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
type LaohuangStage = 'tracking' | 'dropped' | 'rebounded';
type LaohuangTokenState = {
  address: string;
  blacklisted: boolean;
  chain: string;
  currentFdv: number | null;
  currentMarketCap: number | null;
  currentPriceUsd: number | null;
  dropAtMs: number | null;
  dropTriggered: boolean;
  firstSeenAt: string;
  firstSeenAtMs: number;
  firstSeenFdv: number | null;
  growthTriggered: boolean;
  latestNotifiedAt: string;
  latestNotifiedAtMs: number;
  latestSourceKey: string;
  minFdv: number | null;
  reboundAtMs: number | null;
  reboundTriggered: boolean;
  stage: LaohuangStage;
};
type LaohuangSummary = {
  blacklisted: number;
  total: number;
  triggered: number;
  visible: number;
};
type ActiveFilterChip = {
  id:
    | 'chain'
    | 'maxHolders'
    | 'maxMarketCap'
    | 'minCommunityCount'
    | 'minHolders'
    | 'paidOnly'
    | 'search'
    | 'source'
    | 'strategyStatus'
    | 'watchSubscriptions'
    | 'watchTerms'
    | 'watchTransport';
  label: string;
};
type FilterDialogTab = 'basic' | 'watch' | 'strategy' | 'advanced';

interface TokenMarketData {
  priceUsd: number | null;
  marketCap: number | null;
  fdv: number | null;
  liquidityUsd: number | null;
}
type LaohuangStrategyConfig = {
  chain: string;
  dropRatio: number;
  growthPercent: number;
  maxFirstSeenFdv: number;
  reboundDelayMs: number;
  reboundRatio: number;
  requirePaid: boolean;
  seedSourceKey: string;
  trackWindowMs: number;
};

const WATCH_INTERVAL_SEC = 15;
const WATCH_LIMIT = 10;
const MAX_SESSION_NOTIFICATIONS = 250;
const BROWSER_WS_CONNECT_TIMEOUT_MS = 15_000;
const BROWSER_WS_STALE_TIMEOUT_MS = 60_000;
const BROWSER_WS_RECONNECT_DELAY_MS = 3_000;
const MAX_LAOHUANG_HISTORY = 1_000;
const LAOHUANG_MAX_FIRST_SEEN_FDV = 80_000;
const LAOHUANG_DROP_RATIO = 0.5;
const LAOHUANG_REBOUND_RATIO = 1.2;
const LAOHUANG_REBOUND_DELAY_MS = 6_000;
const LAOHUANG_GROWTH_PERCENT = 20;
const LAOHUANG_MAX_TRACK_MS = 12 * 60 * 60 * 1000;
const LAOHUANG_SOURCE_KEY = 'dexscreener.token_profiles_latest';

export function SignalTradeDashboard({
  initialFilters,
  initialNow,
  initialNotifications,
}: DashboardProps): JSX.Element {
  const [filters, setFilters] = useState<DashboardFilters>(initialFilters);
  const [notifications, setNotifications] =
    useState<NotificationRecord[]>(initialNotifications);
  const [laohuangHistory, setLaohuangHistory] = useState<NotificationRecord[]>(
    initialNotifications,
  );
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
  const [filterDialogTab, setFilterDialogTab] = useState<FilterDialogTab>('basic');
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const browserConnectTimersRef = useRef(new Map<string, number>());
  const browserReconnectTimersRef = useRef(new Map<string, number>());
  const browserStaleTimersRef = useRef(new Map<string, number>());
  const browserHttpIntervalRef = useRef<number | null>(null);
  const browserProcessingRef = useRef<Promise<void>>(Promise.resolve());
  const browserSessionRef = useRef(0);
  const browserSocketsRef = useRef(new Map<string, WebSocket>());
  const watchRuntimeRef = useRef<WatchRuntimeState | null>(null);
  // Market-data enrichment cache: "chain:address" → data fetched from DexScreener
  const marketDataCacheRef = useRef(new Map<string, TokenMarketData>());
  const enrichingRef = useRef(new Set<string>());
  const [marketDataVersion, setMarketDataVersion] = useState(0);

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
  const watchTermsList = useMemo(
    () => parseListFilter(filters.watchTerms),
    [filters.watchTerms],
  );

  const laohuangConfig = useMemo(
    () => buildLaohuangConfig(filters),
    [
      filters.strategyDropRatio,
      filters.strategyGrowthPercent,
      filters.strategyMaxFirstSeenFdv,
      filters.strategyReboundDelaySec,
      filters.strategyReboundRatio,
      filters.strategyRequirePaid,
      filters.strategySeedChain,
      filters.strategySeedSubscription,
      filters.strategyTrackHours,
    ],
  );

  const laohuangStates = useMemo(
    () => buildLaohuangState(laohuangHistory, laohuangConfig),
    [laohuangConfig, laohuangHistory],
  );

  const strategyBaseRecords = useMemo(() => {
    if (!isStrategyPresetEnabled(filters.strategyPreset)) {
      return notifications;
    }

    return buildLatestLaohuangRecords(notifications, laohuangStates);
  }, [filters.strategyPreset, laohuangStates, notifications]);

  const laohuangSummary = useMemo(
    () => summarizeLaohuangStates(laohuangStates, relativeNow, laohuangConfig),
    [laohuangConfig, laohuangStates, relativeNow],
  );
  const strategyStatusCounts = useMemo(() => {
    const visibleStates = Object.values(laohuangStates).filter(state =>
      isVisibleLaohuangState(state, relativeNow, laohuangConfig),
    );

    return {
      all: visibleStates.length,
      drop: visibleStates.filter(state => matchesLaohuangStatus(state, 'drop')).length,
      growth: visibleStates.filter(state => matchesLaohuangStatus(state, 'growth')).length,
      rebound: visibleStates.filter(state => matchesLaohuangStatus(state, 'rebound')).length,
      tracking: visibleStates.filter(state => matchesLaohuangStatus(state, 'tracking')).length,
      triggered: visibleStates.filter(state =>
        matchesLaohuangStatus(state, 'triggered'),
      ).length,
    };
  }, [laohuangConfig, laohuangStates, relativeNow]);
  const activeBasicCount =
    Number(filters.search.trim().length > 0) +
    Number(filters.paidOnly) +
    Number(filters.watchTransport !== 'auto') +
    Number(filters.chain !== 'all') +
    Number(filters.source !== 'all');
  const activeWatchCount =
    Number(watchTermsList.length > 0) +
    Number(
      !areStringArraysEqual(selectedWatchSubscriptions, DEFAULT_DEX_WATCH_SUBSCRIPTIONS),
    );
  const activeAdvancedCount =
    Number(filters.minHolders.trim().length > 0) +
    Number(filters.maxHolders.trim().length > 0) +
    Number(filters.maxMarketCap.trim().length > 0) +
    Number(filters.minCommunityCount.trim().length > 0) +
    Number(filters.kolNames.trim().length > 0) +
    Number(filters.followAddresses.trim().length > 0);
  const activeFilterChips = useMemo(() => {
    const chips: ActiveFilterChip[] = [];

    if (filters.search.trim()) {
      chips.push({
        id: 'search',
        label: `搜索 ${truncateText(filters.search.trim(), 18)}`,
      });
    }
    if (filters.paidOnly) {
      chips.push({ id: 'paidOnly', label: '仅 Paid' });
    }
    if (filters.watchTransport !== 'auto') {
      chips.push({ id: 'watchTransport', label: `传输 ${filters.watchTransport}` });
    }
    if (filters.chain !== 'all') {
      chips.push({ id: 'chain', label: `链 ${filters.chain}` });
    }
    if (filters.source !== 'all') {
      chips.push({ id: 'source', label: `来源 ${truncateText(filters.source, 18)}` });
    }
    if (watchTermsList.length > 0) {
      chips.push({ id: 'watchTerms', label: `关键词 ${watchTermsList.length}` });
    }
    if (
      !areStringArraysEqual(selectedWatchSubscriptions, DEFAULT_DEX_WATCH_SUBSCRIPTIONS)
    ) {
      chips.push({
        id: 'watchSubscriptions',
        label: `订阅 ${selectedWatchSubscriptions.length}`,
      });
    }
    if (filters.minHolders.trim()) {
      chips.push({ id: 'minHolders', label: `持币 >= ${filters.minHolders.trim()}` });
    }
    if (filters.maxHolders.trim()) {
      chips.push({ id: 'maxHolders', label: `持币 <= ${filters.maxHolders.trim()}` });
    }
    if (filters.maxMarketCap.trim()) {
      chips.push({
        id: 'maxMarketCap',
        label: `市值 <= ${filters.maxMarketCap.trim()}`,
      });
    }
    if (filters.minCommunityCount.trim()) {
      chips.push({
        id: 'minCommunityCount',
        label: `社区 >= ${filters.minCommunityCount.trim()}`,
      });
    }
    if (isStrategyPresetEnabled(filters.strategyPreset) && filters.strategyStatus !== 'all') {
      chips.push({
        id: 'strategyStatus',
        label: `策略 ${filters.strategyStatus}`,
      });
    }

    return chips;
  }, [
    filters.chain,
    filters.maxHolders,
    filters.maxMarketCap,
    filters.minCommunityCount,
    filters.minHolders,
    filters.paidOnly,
    filters.search,
    filters.source,
    filters.strategyPreset,
    filters.strategyStatus,
    filters.watchTransport,
    selectedWatchSubscriptions,
    watchTermsList,
  ]);

  const filteredNotifications = useMemo(() => {
    const search = deferredSearch.trim().toLowerCase();
    const watchTerms = parseListFilter(deferredWatchTerms);
    const minHolders = parseNumericFilter(filters.minHolders);
    const maxHolders = parseNumericFilter(filters.maxHolders);
    const maxMarketCap = parseNumericFilter(filters.maxMarketCap);
    const minCommunityCount = parseNumericFilter(filters.minCommunityCount);
    return strategyBaseRecords
      .filter(record => {
        const sourceKey = `${record.event.source}.${record.event.subtype}`;
        const laohuangState = getLaohuangStateForRecord(laohuangStates, record);
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
        if (isStrategyPresetEnabled(filters.strategyPreset)) {
          if (
            !laohuangState ||
            !isVisibleLaohuangState(laohuangState, relativeNow, laohuangConfig)
          ) {
            return false;
          }
          if (!matchesLaohuangStatus(laohuangState, filters.strategyStatus)) {
            return false;
          }
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
    filters.strategyPreset,
    filters.strategyStatus,
    laohuangConfig,
    laohuangStates,
    relativeNow,
    strategyBaseRecords,
  ]);

  // Enrich notifications missing market data via DexScreener /tokens/v1 API
  useEffect(() => {
    const toEnrich = new Map<string, string[]>(); // chain → addresses

    for (const record of notifications) {
      const chain = record.event.chain ?? record.context.token?.chain ?? null;
      const address =
        record.context.token?.address ?? record.event.token.address ?? null;
      if (!chain || !address) continue;

      const key = `${chain}:${address}`;
      if (marketDataCacheRef.current.has(key)) continue;
      if (enrichingRef.current.has(key)) continue;

      // Only enrich when both price and market cap are missing
      if (record.summary.priceUsd !== null || record.summary.marketCap !== null) {
        continue;
      }

      enrichingRef.current.add(key);
      if (!toEnrich.has(chain)) toEnrich.set(chain, []);
      toEnrich.get(chain)!.push(address);
    }

    if (toEnrich.size === 0) return;

    let pendingUpdates = 0;

    for (const [chain, addresses] of toEnrich) {
      // Batch into groups of 30 (API limit)
      for (let i = 0; i < addresses.length; i += 30) {
        const batch = addresses.slice(i, i + 30);
        pendingUpdates++;
        void fetch(
          `https://api.dexscreener.com/tokens/v1/${chain}/${batch.join(',')}`,
        )
          .then(r => r.json())
          .then((pairs: unknown) => {
            if (!Array.isArray(pairs)) return;
            for (const pair of pairs) {
              if (!pair || typeof pair !== 'object') continue;
              const p = pair as Record<string, unknown>;
              const baseToken = p['baseToken'] as Record<string, unknown> | undefined;
              const addr =
                typeof baseToken?.['address'] === 'string'
                  ? baseToken['address']
                  : null;
              if (!addr) continue;
              const key = `${chain}:${addr}`;
              const liquidity = p['liquidity'] as Record<string, unknown> | undefined;
              const data: TokenMarketData = {
                priceUsd:
                  typeof p['priceUsd'] === 'string'
                    ? Number(p['priceUsd'])
                    : typeof p['priceUsd'] === 'number'
                      ? p['priceUsd']
                      : null,
                marketCap:
                  typeof p['marketCap'] === 'number' ? p['marketCap'] : null,
                fdv: typeof p['fdv'] === 'number' ? p['fdv'] : null,
                liquidityUsd:
                  typeof liquidity?.['usd'] === 'number' ? liquidity['usd'] : null,
              };
              // Prefer pairs with actual market data (highest liquidity wins)
              const existing = marketDataCacheRef.current.get(key);
              if (
                !existing ||
                (data.liquidityUsd ?? 0) > (existing.liquidityUsd ?? 0)
              ) {
                marketDataCacheRef.current.set(key, data);
              }
            }
          })
          .catch(() => {
            for (const addr of batch) {
              enrichingRef.current.delete(`${chain}:${addr}`);
            }
          })
          .finally(() => {
            pendingUpdates--;
            if (pendingUpdates === 0) {
              setMarketDataVersion(v => v + 1);
            }
          });
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [notifications]);

  function appendNotifications(nextNotifications: NotificationRecord[]): void {
    if (nextNotifications.length === 0) {
      return;
    }

    setLaohuangHistory(current =>
      appendLaohuangHistory(current, nextNotifications),
    );
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

  function updateStrategyFilter<Key extends keyof DashboardFilters>(
    key: Key,
    value: DashboardFilters[Key],
  ): void {
    setFilters(current => ({
      ...current,
      [key]: value,
      strategyPreset:
        current.strategyPreset === 'none' || current.strategyPreset === 'custom'
          ? current.strategyPreset
          : 'custom',
    }));
  }

  function applySelectedStrategyPreset(
    preset: DashboardFilters['strategyPreset'],
  ): void {
    setFilters(current => applyStrategyPreset(current, preset));
  }

  function resetFilters(): void {
    setFilters(initialFilters);
  }

  function clearFilterChip(id: ActiveFilterChip['id']): void {
    if (id === 'search') {
      updateFilter('search', '');
      return;
    }
    if (id === 'paidOnly') {
      updateFilter('paidOnly', false);
      return;
    }
    if (id === 'watchTransport') {
      updateFilter('watchTransport', 'auto');
      return;
    }
    if (id === 'chain') {
      updateFilter('chain', 'all');
      return;
    }
    if (id === 'source') {
      updateFilter('source', 'all');
      return;
    }
    if (id === 'watchTerms') {
      updateFilter('watchTerms', '');
      return;
    }
    if (id === 'watchSubscriptions') {
      updateFilter('watchSubscriptions', [...DEFAULT_DEX_WATCH_SUBSCRIPTIONS]);
      return;
    }
    if (id === 'minHolders') {
      updateFilter('minHolders', '');
      return;
    }
    if (id === 'maxHolders') {
      updateFilter('maxHolders', '');
      return;
    }
    if (id === 'maxMarketCap') {
      updateFilter('maxMarketCap', '');
      return;
    }
    if (id === 'minCommunityCount') {
      updateFilter('minCommunityCount', '');
      return;
    }
    if (id === 'strategyStatus') {
      updateFilter('strategyStatus', 'all');
    }
  }

  const activeStrategyLabel =
    STRATEGY_PRESET_OPTIONS.find(option => option.value === filters.strategyPreset)
      ?.label ?? filters.strategyPreset;
  const transportLabel = watchRuntime?.transport ?? filters.watchTransport;
  const watchStatusLabel = watchRuntime ? formatWatchStatus(watchRuntime) : '待机';
  const activeDialogCount =
    activeBasicCount + activeWatchCount + activeAdvancedCount;

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(91,132,255,0.14),transparent_26%),radial-gradient(circle_at_top_right,rgba(168,85,247,0.08),transparent_20%),linear-gradient(180deg,rgba(255,255,255,0.015),rgba(255,255,255,0))]" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-24 bg-[linear-gradient(180deg,rgba(91,132,255,0.06),transparent)]" />

      <div className="relative mx-auto flex min-h-screen w-full max-w-[1580px] flex-col px-3 pb-8 pt-3 sm:px-4 lg:px-5 lg:pt-4">
        <header className="relative overflow-hidden rounded-[22px] border border-border bg-[linear-gradient(180deg,rgba(11,14,21,0.98),rgba(12,15,23,0.98))] px-4 py-4 shadow-[0_18px_56px_rgba(0,0,0,0.26)] lg:px-5">
          <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-[linear-gradient(90deg,transparent,rgba(91,132,255,0.55),transparent)]" />
          <div className="pointer-events-none absolute -right-10 top-0 h-32 w-32 rounded-full bg-[rgba(91,132,255,0.08)] blur-3xl" />
            <div className="space-y-2">
              <Badge className="w-fit gap-2 rounded-full bg-[rgba(12,15,23,0.96)] px-3 py-1.5 text-[10px] text-[#9ab4ff]">
                <BellRing className="size-3" />
                Signal Trade // Scan Desk
              </Badge>

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
              <RefreshChip refreshState={refreshState} />
              <WatchChip watchRuntime={watchRuntime} />
            </div>
            <div className="grid gap-2 md:grid-cols-3">
              <ControlMetricCard
                label="会话流"
                value={String(notifications.length)}
                detail="当前页面会话通知"
              />
              <ControlMetricCard
                label="命中结果"
                value={String(filteredNotifications.length)}
                detail="当前筛选后结果"
              />
              <ControlMetricCard
                label="策略"
                value={activeStrategyLabel}
                detail={
                  isStrategyPresetEnabled(filters.strategyPreset)
                    ? `Triggered ${laohuangSummary.triggered}`
                    : 'Disabled'
                }
              />
            </div>
            {refreshSummary ? (
              <p className="rounded-[16px] border border-border/70 bg-[rgba(14,18,27,0.92)] px-3 py-2 text-xs leading-5 text-muted-foreground">
                {refreshSummary}
              </p>
            ) : null}
          </div>
        </header>

        <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(560px,0.92fr)_minmax(0,1.08fr)]">
          <Card className="overflow-hidden xl:sticky xl:top-4 xl:self-start">
            <CardHeader className="border-b border-border/70 bg-[rgba(11,14,21,0.92)]">
              <div className="flex items-center justify-between gap-3">
                <CardTitle className="flex items-center gap-2 text-xl">
                  <Filter className="size-5 text-[color:var(--color-accent)]" />
                  扫链控制台
                </CardTitle>
                <button
                  type="button"
                  className={cn(
                    'flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors',
                    activeDialogCount > 0
                      ? 'border-[color:var(--color-accent)] bg-[rgba(91,132,255,0.12)] text-foreground'
                      : 'border-border bg-[rgba(14,18,27,0.92)] text-muted-foreground hover:text-foreground',
                  )}
                  onClick={() => setAdvancedOpen(true)}
                >
                  <SlidersHorizontal className="size-3" />
                  筛选
                  {activeDialogCount > 0 ? (
                    <span className="rounded-full border border-white/[0.08] bg-black/20 px-1.5 py-0.5 text-[10px] leading-none text-muted-foreground">
                      {activeDialogCount}
                    </span>
                  ) : null}
                </button>
              </div>
              <div className="mt-3 grid gap-3 xl:grid-cols-[minmax(0,1.45fr)_repeat(2,minmax(0,0.85fr))]">
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
                <FieldGroup label="监听模式">
                  <SelectField
                    options={['auto', 'ws', 'http']}
                    value={filters.watchTransport}
                    onChange={value =>
                      updateFilter(
                        'watchTransport',
                        value as DashboardFilters['watchTransport'],
                      )
                    }
                  />
                </FieldGroup>
                <FieldGroup label="策略预设">
                  <SelectField
                    options={STRATEGY_PRESET_OPTIONS.map(option => ({
                      label: option.label,
                      value: option.value,
                    }))}
                    value={filters.strategyPreset}
                    onChange={value =>
                      applySelectedStrategyPreset(
                        value as DashboardFilters['strategyPreset'],
                      )
                    }
                  />
                </FieldGroup>
              </div>
            </CardHeader>
            <CardContent className="pt-4 space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <Button className="w-full rounded-full" variant="outline" onClick={resetFilters}>
                  重置筛选
                </Button>
                <Button
                  className="w-full rounded-full"
                  disabled={isWatchMutating}
                  variant="secondary"
                  onClick={() => {
                    void startWatch();
                  }}
                >
                  {watchRuntime?.running ? '重启监听' : '启动监听'}
                </Button>
                <Button
                  className="w-full rounded-full"
                  disabled={isWatchMutating || !watchRuntime?.running}
                  variant="outline"
                  onClick={() => {
                    void stopWatch();
                  }}
                >
                  停止监听
                </Button>
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
                  诊断
                </Button>
              </div>
            </CardContent>
          </Card>

          <Dialog
            open={advancedOpen}
            title="筛选设置"
            onClose={() => setAdvancedOpen(false)}
          >
            {/* Tab bar */}
            <div className="mb-4 flex flex-wrap gap-2 border-b border-border/60 pb-3">
              {(
                [
                  { id: 'basic', label: '基础', count: activeBasicCount },
                  { id: 'watch', label: '监听', count: activeWatchCount },
                  ...(isStrategyPresetEnabled(filters.strategyPreset)
                    ? [{ id: 'strategy', label: '策略', count: strategyStatusCounts.triggered }]
                    : []),
                  { id: 'advanced', label: '高级', count: activeAdvancedCount },
                ] as Array<{ id: FilterDialogTab; label: string; count: number }>
              ).map(tab => (
                <button
                  key={tab.id}
                  type="button"
                  className={cn(
                    'rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors',
                    filterDialogTab === tab.id
                      ? 'border-[color:var(--color-accent)] bg-[rgba(91,132,255,0.12)] text-foreground'
                      : 'border-border bg-[rgba(14,18,27,0.92)] text-muted-foreground hover:text-foreground',
                  )}
                  onClick={() => setFilterDialogTab(tab.id)}
                >
                  <span className="flex items-center gap-2">
                    {tab.label}
                    {tab.count > 0 ? (
                      <span className="rounded-full border border-white/[0.08] bg-black/20 px-1.5 py-0.5 text-[10px] leading-none text-muted-foreground">
                        {tab.count}
                      </span>
                    ) : null}
                  </span>
                </button>
              ))}
            </div>

            {/* 基础 tab */}
            {filterDialogTab === 'basic' ? (
              <div className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-2">
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
                </div>
                <button
                  type="button"
                  className={cn(
                    'flex w-full items-center justify-between rounded-[18px] border px-4 py-3 text-left transition-colors',
                    filters.paidOnly
                      ? 'border-[color:var(--color-accent)] bg-[rgba(91,132,255,0.12)] shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]'
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
              </div>
            ) : null}

            {/* 监听 tab */}
            {filterDialogTab === 'watch' ? (
              <div className="space-y-4">
                <FieldGroup label="观察名单关键词">
                  <Textarea
                    className="min-h-[72px]"
                    placeholder="支持逗号或换行，例如：ansem, base, hype"
                    value={filters.watchTerms}
                    onChange={event => updateFilter('watchTerms', event.target.value)}
                  />
                </FieldGroup>
                <div className="space-y-2.5">
                  <Label>WS 订阅</Label>
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
                </div>
              </div>
            ) : null}

            {/* 策略 tab */}
            {filterDialogTab === 'strategy' && isStrategyPresetEnabled(filters.strategyPreset) ? (
              <div className="space-y-4">
                <p className="text-xs leading-6 text-muted-foreground">
                  会话内跟踪 {laohuangSummary.visible} 个 token，命中异常{' '}
                  {laohuangSummary.triggered} 个，首推超{' '}
                  {formatUsd(laohuangConfig.maxFirstSeenFdv)} 被隐藏{' '}
                  {laohuangSummary.blacklisted} 个。
                </p>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  <FieldGroup label="种子订阅">
                    <SelectField
                      options={DEX_WATCH_SUBSCRIPTION_OPTIONS.map(option => ({
                        label: option.label,
                        value: option.id,
                      }))}
                      value={filters.strategySeedSubscription}
                      onChange={value =>
                        updateStrategyFilter('strategySeedSubscription', value)
                      }
                    />
                  </FieldGroup>
                  <FieldGroup label="种子链">
                    <Input
                      placeholder="solana"
                      value={filters.strategySeedChain}
                      onChange={event =>
                        updateStrategyFilter('strategySeedChain', event.target.value)
                      }
                    />
                  </FieldGroup>
                  <FieldGroup label="首推 FDV 上限">
                    <Input
                      inputMode="decimal"
                      placeholder="80000"
                      value={filters.strategyMaxFirstSeenFdv}
                      onChange={event =>
                        updateStrategyFilter(
                          'strategyMaxFirstSeenFdv',
                          event.target.value,
                        )
                      }
                    />
                  </FieldGroup>
                  <FieldGroup label="跟踪窗口小时">
                    <Input
                      inputMode="decimal"
                      placeholder="12"
                      value={filters.strategyTrackHours}
                      onChange={event =>
                        updateStrategyFilter('strategyTrackHours', event.target.value)
                      }
                    />
                  </FieldGroup>
                  <FieldGroup label="下跌比例">
                    <Input
                      inputMode="decimal"
                      placeholder="0.5"
                      value={filters.strategyDropRatio}
                      onChange={event =>
                        updateStrategyFilter('strategyDropRatio', event.target.value)
                      }
                    />
                  </FieldGroup>
                  <FieldGroup label="回调倍数">
                    <Input
                      inputMode="decimal"
                      placeholder="1.2"
                      value={filters.strategyReboundRatio}
                      onChange={event =>
                        updateStrategyFilter('strategyReboundRatio', event.target.value)
                      }
                    />
                  </FieldGroup>
                  <FieldGroup label="回调延迟秒数">
                    <Input
                      inputMode="decimal"
                      placeholder="6"
                      value={filters.strategyReboundDelaySec}
                      onChange={event =>
                        updateStrategyFilter(
                          'strategyReboundDelaySec',
                          event.target.value,
                        )
                      }
                    />
                  </FieldGroup>
                  <FieldGroup label="涨幅阈值 %">
                    <Input
                      inputMode="decimal"
                      placeholder="20"
                      value={filters.strategyGrowthPercent}
                      onChange={event =>
                        updateStrategyFilter(
                          'strategyGrowthPercent',
                          event.target.value,
                        )
                      }
                    />
                  </FieldGroup>
                </div>
                <button
                  type="button"
                  className={cn(
                    'flex w-full items-center justify-between rounded-[18px] border px-4 py-3 text-left transition-colors',
                    filters.strategyRequirePaid
                      ? 'border-[color:var(--color-accent)] bg-[rgba(91,132,255,0.12)] shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]'
                      : 'border-border bg-[color:var(--color-panel-soft)]',
                  )}
                  onClick={() =>
                    updateStrategyFilter(
                      'strategyRequirePaid',
                      !filters.strategyRequirePaid,
                    )
                  }
                >
                  <div>
                    <p className="text-sm font-semibold text-foreground">
                      种子必须是 Paid
                    </p>
                    <p className="text-xs text-muted-foreground">
                      关闭后，只按订阅 + 链来当作策略种子。
                    </p>
                  </div>
                  <Badge variant={filters.strategyRequirePaid ? 'success' : 'secondary'}>
                    {filters.strategyRequirePaid ? 'ON' : 'OFF'}
                  </Badge>
                </button>
              </div>
            ) : null}

            {/* 高级 tab */}
            {filterDialogTab === 'advanced' ? (
              <div className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-2">
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
                      onChange={event => updateFilter('minCommunityCount', event.target.value)}
                    />
                  </FieldGroup>
                </div>

                <DiagnosticsPanel
                  diagnostics={diagnostics}
                  diagnosticsError={diagnosticsError}
                />
              </div>
            ) : null}
          </Dialog>

          <section className="overflow-hidden rounded-[24px] border border-border bg-[linear-gradient(180deg,rgba(10,12,19,0.98),rgba(8,10,16,0.98))] shadow-[0_18px_56px_rgba(0,0,0,0.24)]">
            <div className="border-b border-border/70 bg-[rgba(11,14,21,0.92)] px-5 py-4 sm:px-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 text-xl font-semibold text-foreground">
                    <Layers className="size-5 text-[color:var(--color-accent)]" />
                    扫链结果
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">
                    当前页面会话累计记录 {notifications.length} 条通知，筛选后显示{' '}
                    {filteredNotifications.length} 条。
                    {isStrategyPresetEnabled(filters.strategyPreset)
                      ? ` 当前按 token 去重，并使用策略状态机过滤。`
                      : ''}
                  </p>
                  {activeFilterChips.length > 0 ? (
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      {activeFilterChips.map(chip => (
                        <button
                          key={chip.id}
                          type="button"
                          className="inline-flex items-center gap-1 rounded-full border border-border bg-[rgba(14,18,27,0.92)] px-3 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
                          onClick={() => {
                            clearFilterChip(chip.id);
                          }}
                        >
                          {chip.label}
                          <span className="text-foreground/70">x</span>
                        </button>
                      ))}
                      <button
                        type="button"
                        className="inline-flex items-center rounded-full border border-[color:var(--color-accent)] bg-[rgba(91,132,255,0.12)] px-3 py-1 text-xs text-foreground"
                        onClick={resetFilters}
                      >
                        清空筛选
                      </button>
                    </div>
                  ) : (
                    <p className="mt-3 text-xs text-muted-foreground">
                      当前没有额外筛选，结果按最新通知时间排序。
                    </p>
                  )}
                </div>
                {isStrategyPresetEnabled(filters.strategyPreset) ? (
                  <div className="flex flex-wrap gap-2">
                    {[
                      ['all', '全部', strategyStatusCounts.all],
                      ['tracking', '跟踪', strategyStatusCounts.tracking],
                      ['drop', '下跌', strategyStatusCounts.drop],
                      ['rebound', '回调', strategyStatusCounts.rebound],
                      ['growth', '上涨', strategyStatusCounts.growth],
                      ['triggered', '触发', strategyStatusCounts.triggered],
                    ].map(([value, label, count]) => (
                      <button
                        key={value}
                        type="button"
                        className={cn(
                          'inline-flex items-center rounded-full border px-3 py-1 text-xs transition-colors',
                          filters.strategyStatus === value
                            ? 'border-[color:var(--color-accent)] bg-[rgba(91,132,255,0.12)] text-foreground'
                            : 'border-border bg-[rgba(14,18,27,0.92)] text-muted-foreground hover:text-foreground',
                        )}
                        onClick={() => {
                          updateFilter(
                            'strategyStatus',
                            value as DashboardFilters['strategyStatus'],
                          );
                        }}
                      >
                        {label} {count}
                      </button>
                    ))}
                    <Badge variant="outline" className="normal-case tracking-normal">
                      hidden {laohuangSummary.blacklisted}
                    </Badge>
                  </div>
                ) : null}
              </div>
            </div>
            <div className="p-3 sm:p-4">
              {filteredNotifications.length > 0 ? (
                <ol className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {filteredNotifications.map(record => (
                    <NotificationListItem
                      key={record.id}
                      currentTimeMs={relativeNow}
                      marketDataVersion={marketDataVersion}
                      enrichedMarketData={(() => {
                        const chain = record.event.chain ?? record.context.token?.chain ?? null;
                        const address = record.context.token?.address ?? record.event.token.address ?? null;
                        if (!chain || !address) return null;
                        return marketDataCacheRef.current.get(`${chain}:${address}`) ?? null;
                      })()}
                      record={record}
                      strategyPreset={filters.strategyPreset}
                      strategyState={getLaohuangStateForRecord(laohuangStates, record)}
                    />
                  ))}
                </ol>
              ) : (
                <EmptyState
                  activeFilterCount={activeFilterChips.length}
                  onResetFilters={resetFilters}
                />
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
    <Badge
      variant="secondary"
      className="border border-border px-3 py-1.5 normal-case tracking-normal"
    >
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

function ControlMetricCard({
  detail,
  label,
  value,
}: {
  detail: string;
  label: string;
  value: string;
}): JSX.Element {
  return (
    <div className="rounded-[16px] border border-border bg-[rgba(15,18,27,0.92)] px-3 py-2">
      <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 truncate text-base font-semibold tracking-[-0.04em] text-foreground">
        {value}
      </p>
      <p className="mt-0.5 text-[10px] text-muted-foreground">{detail}</p>
    </div>
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
      ? 'border-red-500/30 bg-[rgba(86,23,28,0.72)] text-red-200'
      : 'border-border bg-[rgba(14,18,27,0.92)] text-muted-foreground';

  return (
    <div className={cn('rounded-[18px] border px-4 py-3 text-xs leading-6', toneClass)}>
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
    <div className="rounded-[18px] border border-border bg-[rgba(14,18,27,0.92)] px-4 py-3 text-xs leading-6 text-muted-foreground">
      <p className="font-semibold text-foreground">网络诊断</p>
      {diagnosticsError ? (
        <p className="mt-2 break-all text-red-300">执行失败：{diagnosticsError}</p>
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
  enrichedMarketData,
  marketDataVersion: _marketDataVersion,
  record,
  strategyPreset,
  strategyState,
}: {
  currentTimeMs: number;
  enrichedMarketData: TokenMarketData | null;
  marketDataVersion: number;
  record: NotificationRecord;
  strategyPreset: DashboardFilters['strategyPreset'];
  strategyState: LaohuangTokenState | null;
}): JSX.Element {
  const sourceKey = `${record.event.source}.${record.event.subtype}`;
  const displayAddress =
    record.context.token?.address || record.event.token.address || null;
  const displaySymbol =
    record.context.token?.symbol ||
    record.event.token.symbol ||
    (displayAddress ? truncateMiddle(displayAddress, 6, 4).toUpperCase() : 'UNKNOWN');
  const displayName =
    record.context.token?.name || record.event.token.name || null;
  const [addressCopied, setAddressCopied] = useState(false);
  const rawDisplayText =
    record.context.dexscreener?.description ||
    record.context.dexscreener?.header ||
    record.event.text ||
    record.message;
  // Filter out raw URLs (CDN/image links) that aren't useful as descriptions
  const displayText = rawDisplayText?.startsWith('http') ? null : rawDisplayText;
  const rawAmount = asOptionalNumber(record.event.metrics?.amount);
  const rawTotalAmount = asOptionalNumber(record.event.metrics?.totalAmount);
  const rawActiveBoosts = asOptionalNumber(record.event.metrics?.activeBoosts);
  const twitterProfileUrl = record.context.twitter?.profile_url ?? null;
  const strategyEnabled =
    isStrategyPresetEnabled(strategyPreset) && strategyState !== null;
  const currentMarketCap = strategyEnabled
    ? (strategyState.currentMarketCap ?? enrichedMarketData?.marketCap ?? null)
    : (record.summary.marketCap ?? enrichedMarketData?.marketCap ?? null);
  const currentPriceUsd = strategyEnabled
    ? (strategyState.currentPriceUsd ?? enrichedMarketData?.priceUsd ?? null)
    : (record.summary.priceUsd ?? enrichedMarketData?.priceUsd ?? null);
  const currentFdv = strategyEnabled
    ? (strategyState.currentFdv ?? enrichedMarketData?.fdv ?? null)
    : (asOptionalNumber(record.context.dexscreener?.fdv) ?? enrichedMarketData?.fdv ?? null);
  const enrichedLiquidityUsd =
    record.summary.liquidityUsd ?? enrichedMarketData?.liquidityUsd ?? null;
  const strategyChangePercent = strategyEnabled
    ? getLaohuangChangePercent(strategyState)
    : null;
  const strategyBadges = strategyEnabled ? getLaohuangBadges(strategyState) : [];

  return (
    <li
      className={cn(
        'flex h-full flex-col rounded-[18px] border border-border bg-[linear-gradient(180deg,rgba(12,15,23,0.98),rgba(9,12,18,0.98))] p-3 shadow-[0_10px_24px_rgba(0,0,0,0.16)] transition-colors hover:border-white/[0.12] hover:bg-[linear-gradient(180deg,rgba(15,19,29,0.98),rgba(10,13,20,0.98))]',
        strategyEnabled ? getLaohuangToneClass(strategyState) : '',
      )}
    >
      <div className="flex h-full flex-col gap-2.5">
        <div className="flex min-w-0 items-start gap-3">
          <TokenAvatar
            imageUrl={record.summary.imageUrl}
            symbol={displaySymbol}
          />
          <div className="min-w-0 flex-1">
            <div className="flex items-baseline justify-between gap-2">
              <p className="truncate text-base font-semibold tracking-[-0.03em] text-foreground">
                {displaySymbol}
              </p>
              <span className="shrink-0 font-mono text-[11px] text-muted-foreground">
                {formatRelativeTime(record.notifiedAt, currentTimeMs)}
              </span>
            </div>
            {displayName ? (
              <p className="mt-1 truncate text-sm text-foreground/80">{displayName}</p>
            ) : null}
            {displayAddress ? (
              <button
                type="button"
                className="mt-1 flex items-center gap-1.5 font-mono text-[11px] text-muted-foreground transition-colors hover:text-foreground"
                title={addressCopied ? '已复制' : '点击复制合约地址'}
                onClick={() => {
                  void navigator.clipboard.writeText(displayAddress).then(() => {
                    setAddressCopied(true);
                    setTimeout(() => { setAddressCopied(false); }, 1500);
                  });
                }}
              >
                {addressCopied ? (
                  <Check className="size-3 text-green-400" />
                ) : (
                  <Copy className="size-3" />
                )}
                {truncateMiddle(displayAddress, 8, 6)}
              </button>
            ) : null}
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Badge variant={record.summary.paid ? 'success' : 'secondary'}>
            {record.summary.paid ? 'paid' : 'organic'}
          </Badge>
          {strategyEnabled ? (
            <Badge variant="outline" className="tracking-[0.12em]">
              strategy
            </Badge>
          ) : null}
          {strategyEnabled
            ? strategyBadges.map(badge => (
                <Badge
                  key={badge.label}
                  className={badge.className}
                  variant={badge.variant}
                >
                  {badge.label}
                </Badge>
              ))
            : null}
          <span className="rounded-full border border-border/60 bg-[rgba(14,18,27,0.92)] px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
            {record.event.chain || 'n/a'}
          </span>
        </div>

        <div className="flex flex-wrap gap-2">
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

        {strategyEnabled ? (
          <div className="flex flex-wrap gap-2">
            <InfoPill
              icon={Layers}
              label={`首推 FDV ${formatUsd(strategyState.firstSeenFdv)}`}
            />
            <InfoPill
              icon={Target}
              label={`首推 ${formatAbsoluteTime(strategyState.firstSeenAt)}`}
            />
            <InfoPill
              icon={Activity}
              label={`相对首推 ${formatSignedPercent(strategyChangePercent)}`}
            />
          </div>
        ) : null}

        <div className="grid gap-2.5 text-sm">
          {displayText ? (
            <p className="text-[13px] leading-5 text-muted-foreground">
              {displayText}
            </p>
          ) : null}
          {(currentMarketCap !== null ||
            enrichedLiquidityUsd !== null ||
            currentPriceUsd !== null ||
            currentFdv !== null ||
            rawAmount !== null ||
            rawTotalAmount !== null) ? (
            <dl className="grid grid-cols-2 gap-2 text-right">
              <MetricPair label="市值" value={formatUsd(currentMarketCap)} />
              <MetricPair
                label="流动性"
                value={formatUsd(enrichedLiquidityUsd)}
              />
              <MetricPair
                label="价格"
                value={formatPriceUsd(currentPriceUsd)}
              />
              <MetricPair
                label="FDV"
                value={formatUsd(currentFdv)}
              />

            </dl>
          ) : null}
        </div>

        <div className="mt-auto flex flex-wrap gap-2">
          {record.summary.twitterUsername && twitterProfileUrl ? (
            <a
              className="inline-flex items-center gap-1 rounded-full border border-border bg-[rgba(14,18,27,0.92)] px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-[color:var(--color-panel-soft)]"
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
              className="inline-flex items-center gap-1 rounded-full border border-border bg-[rgba(14,18,27,0.92)] px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-[color:var(--color-panel-soft)]"
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
              className="inline-flex items-center gap-1 rounded-full border border-border bg-[rgba(14,18,27,0.92)] px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-[color:var(--color-panel-soft)]"
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
        className="size-12 rounded-[16px] border border-border/80 bg-[rgba(14,18,27,0.92)] object-cover"
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
    <div className="flex size-12 items-center justify-center rounded-[16px] border border-border/80 bg-[rgba(14,18,27,0.92)] text-sm font-semibold text-foreground">
      {label}
    </div>
  );
}

function EmptyState({
  activeFilterCount,
  onResetFilters,
}: {
  activeFilterCount: number;
  onResetFilters: () => void;
}): JSX.Element {
  return (
    <div className="px-6 py-10">
      <div className="flex min-h-[280px] flex-col items-center justify-center rounded-[22px] border border-dashed border-border bg-[rgba(14,18,27,0.92)] px-6 py-10 text-center">
        <div className="rounded-full bg-[rgba(91,132,255,0.12)] p-4 text-[color:var(--color-accent)]">
          <BellRing className="size-8" />
        </div>
        <h3 className="mt-5 text-2xl font-semibold tracking-[-0.04em] text-foreground">
          当前没有符合筛选条件的通知
        </h3>
        <p className="mt-3 max-w-md text-sm leading-6 text-muted-foreground">
          {activeFilterCount > 0
            ? `当前还有 ${activeFilterCount} 个生效筛选。你可以先清掉筛选，或者切回左侧面板调整条件。`
            : '你可以直接同步一次通知，或者启动 `ws / http` 监听，把新通知写入当前页面会话。'}
        </p>
        <div className="mt-5 flex flex-wrap justify-center gap-3">
          <Button className="rounded-full" variant="outline" onClick={onResetFilters}>
            清空筛选
          </Button>
        </div>
      </div>
    </div>
  );
}

function MetricPair({
  label,
  value,
}: {
  label: string;
  value: string | null;
}): JSX.Element | null {
  if (value === null) return null;
  return (
    <div className="min-w-0 overflow-hidden rounded-[14px] border border-border/70 bg-[rgba(14,18,27,0.92)] px-3 py-2">
      <dt className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-1 break-words font-mono text-xs font-semibold text-foreground">{value}</dd>
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
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border/70 bg-[rgba(14,18,27,0.92)] px-2.5 py-1 text-[11px] font-medium text-muted-foreground">
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

function ControlSection({
  children,
  title,
  trailing,
}: {
  children: ReactNode;
  title: string;
  trailing?: ReactNode;
}): JSX.Element {
  return (
    <section className="space-y-3 rounded-[18px] border border-border bg-[rgba(13,16,24,0.92)] p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        {trailing}
      </div>
      {children}
    </section>
  );
}

function SelectField({
  onChange,
  options,
  value,
}: {
  onChange: (value: string) => void;
  options: Array<string | { label: string; value: string }>;
  value: string;
}): JSX.Element {
  return (
    <div className="relative">
      <select
        className="h-10 w-full appearance-none rounded-xl border border-border bg-[rgba(9,11,17,0.92)] px-3.5 py-2 text-sm text-foreground outline-none transition-colors shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] focus:border-[color:var(--color-accent)] focus:bg-[rgba(13,16,24,0.98)]"
        onChange={event => onChange(event.target.value)}
        value={value}
      >
        {options.map(option => (
          <option
            key={typeof option === 'string' ? option : option.value}
            value={typeof option === 'string' ? option : option.value}
          >
            {typeof option === 'string' ? option : option.label}
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
              'flex w-full items-center justify-between rounded-[18px] border px-4 py-3 text-left transition-colors',
              selected
                ? 'border-[color:var(--color-accent)] bg-[rgba(91,132,255,0.12)] shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]'
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

function buildLaohuangState(
  records: NotificationRecord[],
  config: LaohuangStrategyConfig,
): Record<string, LaohuangTokenState> {
  return reduceLaohuangState({}, records, config);
}

function appendLaohuangHistory(
  current: NotificationRecord[],
  incoming: NotificationRecord[],
): NotificationRecord[] {
  return [...current, ...incoming].slice(-MAX_LAOHUANG_HISTORY);
}

function buildLaohuangConfig(
  filters: DashboardFilters,
): LaohuangStrategyConfig {
  const maxFirstSeenFdv = parseNumericFilter(filters.strategyMaxFirstSeenFdv);
  const dropRatio = parseNumericFilter(filters.strategyDropRatio);
  const reboundRatio = parseNumericFilter(filters.strategyReboundRatio);
  const reboundDelaySec = parseNumericFilter(filters.strategyReboundDelaySec);
  const growthPercent = parseNumericFilter(filters.strategyGrowthPercent);
  const trackHours = parseNumericFilter(filters.strategyTrackHours);
  const normalizedSeedChain =
    normalizeStrategyValue(filters.strategySeedChain)?.toLowerCase() ?? 'solana';
  const seedSubscription =
    normalizeStrategyValue(filters.strategySeedSubscription) ?? 'token_profiles_latest';

  return {
    chain: normalizedSeedChain,
    dropRatio: dropRatio !== null && dropRatio > 0 ? dropRatio : LAOHUANG_DROP_RATIO,
    growthPercent:
      growthPercent !== null ? growthPercent : LAOHUANG_GROWTH_PERCENT,
    maxFirstSeenFdv:
      maxFirstSeenFdv !== null && maxFirstSeenFdv > 0
        ? maxFirstSeenFdv
        : LAOHUANG_MAX_FIRST_SEEN_FDV,
    reboundDelayMs:
      reboundDelaySec !== null && reboundDelaySec >= 0
        ? reboundDelaySec * 1000
        : LAOHUANG_REBOUND_DELAY_MS,
    reboundRatio:
      reboundRatio !== null && reboundRatio > 0
        ? reboundRatio
        : LAOHUANG_REBOUND_RATIO,
    requirePaid: filters.strategyRequirePaid,
    seedSourceKey: seedSubscription.includes('.')
      ? seedSubscription
      : seedSubscription
        ? `dexscreener.${seedSubscription}`
        : LAOHUANG_SOURCE_KEY,
    trackWindowMs:
      trackHours !== null && trackHours > 0
        ? trackHours * 60 * 60 * 1000
        : LAOHUANG_MAX_TRACK_MS,
  };
}

function reduceLaohuangState(
  current: Record<string, LaohuangTokenState>,
  incoming: NotificationRecord[],
  config: LaohuangStrategyConfig,
): Record<string, LaohuangTokenState> {
  const next = { ...current };
  const ordered = [...incoming].sort(
    (left, right) =>
      new Date(left.notifiedAt).getTime() - new Date(right.notifiedAt).getTime(),
  );

  for (const record of ordered) {
    const tokenKey = getNotificationTokenKey(record);
    const address =
      normalizeStrategyValue(record.context.token?.address) ??
      normalizeStrategyValue(record.event.token.address);
    const chain = normalizeStrategyValue(record.event.chain)?.toLowerCase() ?? 'unknown';
    const sourceKey = `${record.event.source}.${record.event.subtype}`;
    const notifiedAtMs = new Date(record.notifiedAt).getTime();
    const fdv = readLaohuangFdv(record);
    const marketCap = asOptionalNumber(record.summary.marketCap);
    const priceUsd =
      asOptionalNumber(record.summary.priceUsd) ??
      asOptionalNumber(record.context.dexscreener?.priceUsd);
    const isSeedRecord = isLaohuangSeedRecord(record, config);

    if (!tokenKey || !address) {
      continue;
    }

    let state = next[tokenKey];
    if (!state) {
      if (!isSeedRecord) {
        continue;
      }

      state = {
        address,
        blacklisted: false,
        chain,
        currentFdv: fdv,
        currentMarketCap: marketCap,
        currentPriceUsd: priceUsd,
        dropAtMs: null,
        dropTriggered: false,
        firstSeenAt: record.notifiedAt,
        firstSeenAtMs: notifiedAtMs,
        firstSeenFdv: fdv,
        growthTriggered: false,
        latestNotifiedAt: record.notifiedAt,
        latestNotifiedAtMs: notifiedAtMs,
        latestSourceKey: sourceKey,
        minFdv: null,
        reboundAtMs: null,
        reboundTriggered: false,
        stage: 'tracking',
      };
      next[tokenKey] = state;
    } else {
      state = { ...state };
      next[tokenKey] = state;
    }

    if (isSeedRecord && notifiedAtMs < state.firstSeenAtMs) {
      state.firstSeenAt = record.notifiedAt;
      state.firstSeenAtMs = notifiedAtMs;
      state.firstSeenFdv = fdv;
    } else if (isSeedRecord && state.firstSeenFdv === null && fdv !== null) {
      state.firstSeenFdv = fdv;
    }

    if (isSeedRecord && state.firstSeenFdv !== null) {
      state.blacklisted = state.firstSeenFdv > config.maxFirstSeenFdv;
    }

    if (notifiedAtMs >= state.latestNotifiedAtMs) {
      state.latestNotifiedAt = record.notifiedAt;
      state.latestNotifiedAtMs = notifiedAtMs;
      state.latestSourceKey = sourceKey;
      if (fdv !== null) {
        state.currentFdv = fdv;
      }
      if (marketCap !== null) {
        state.currentMarketCap = marketCap;
      }
      if (priceUsd !== null) {
        state.currentPriceUsd = priceUsd;
      }
    } else {
      if (state.currentFdv === null && fdv !== null) {
        state.currentFdv = fdv;
      }
      if (state.currentMarketCap === null && marketCap !== null) {
        state.currentMarketCap = marketCap;
      }
      if (state.currentPriceUsd === null && priceUsd !== null) {
        state.currentPriceUsd = priceUsd;
      }
    }

    if (
      state.blacklisted ||
      fdv === null ||
      state.firstSeenFdv === null ||
      state.firstSeenFdv <= 0
    ) {
      continue;
    }

    let triggeredThisRecord = false;
    const dropFdv = state.firstSeenFdv * config.dropRatio;

    if (state.stage === 'tracking' && fdv <= dropFdv) {
      state.dropTriggered = true;
      state.stage = 'dropped';
      state.dropAtMs = notifiedAtMs;
      state.minFdv = fdv;
      triggeredThisRecord = true;
    } else if (state.stage === 'dropped') {
      if (state.minFdv === null || fdv < state.minFdv) {
        state.minFdv = fdv;
      } else if (
        !state.reboundTriggered &&
        state.dropAtMs !== null &&
        state.minFdv > 0 &&
        notifiedAtMs >= state.dropAtMs + config.reboundDelayMs &&
        fdv >= state.minFdv * config.reboundRatio
      ) {
        state.reboundTriggered = true;
        state.stage = 'rebounded';
        state.reboundAtMs = notifiedAtMs;
        triggeredThisRecord = true;
      }
    }

    const changePercent = ((fdv - state.firstSeenFdv) / state.firstSeenFdv) * 100;
    if (!triggeredThisRecord && !state.growthTriggered && changePercent >= config.growthPercent) {
      state.growthTriggered = true;
    }
  }

  return next;
}

function summarizeLaohuangStates(
  states: Record<string, LaohuangTokenState>,
  nowMs: number,
  config: LaohuangStrategyConfig,
): LaohuangSummary {
  const values = Object.values(states);
  const visible = values.filter(state =>
    isVisibleLaohuangState(state, nowMs, config),
  );
  const triggered = visible.filter(state =>
    matchesLaohuangStatus(state, 'triggered'),
  );

  return {
    blacklisted: values.filter(state => state.blacklisted).length,
    total: values.length,
    triggered: triggered.length,
    visible: visible.length,
  };
}

function buildLatestLaohuangRecords(
  notifications: NotificationRecord[],
  states: Record<string, LaohuangTokenState>,
): NotificationRecord[] {
  const latestByToken = new Map<string, NotificationRecord>();

  for (const record of notifications) {
    const tokenKey = getNotificationTokenKey(record);
    if (!tokenKey || !states[tokenKey]) {
      continue;
    }

    const existing = latestByToken.get(tokenKey);
    if (!existing) {
      latestByToken.set(tokenKey, record);
      continue;
    }

    if (
      new Date(record.notifiedAt).getTime() >
      new Date(existing.notifiedAt).getTime()
    ) {
      latestByToken.set(tokenKey, record);
    }
  }

  return Array.from(latestByToken.values());
}

function getLaohuangStateForRecord(
  states: Record<string, LaohuangTokenState>,
  record: NotificationRecord,
): LaohuangTokenState | null {
  const tokenKey = getNotificationTokenKey(record);
  if (!tokenKey) {
    return null;
  }

  return states[tokenKey] ?? null;
}

function getNotificationTokenKey(record: NotificationRecord): string | null {
  const chain = normalizeStrategyValue(record.event.chain)?.toLowerCase();
  const address =
    normalizeStrategyValue(record.context.token?.address) ??
    normalizeStrategyValue(record.event.token.address);

  if (!chain || !address) {
    return null;
  }

  return `${chain}:${address.toLowerCase()}`;
}

function isLaohuangSeedRecord(
  record: NotificationRecord,
  config: LaohuangStrategyConfig,
): boolean {
  const chain = normalizeStrategyValue(record.event.chain)?.toLowerCase();
  return (
    chain === config.chain &&
    `${record.event.source}.${record.event.subtype}` === config.seedSourceKey &&
    (!config.requirePaid || record.summary.paid)
  );
}

function isVisibleLaohuangState(
  state: LaohuangTokenState,
  nowMs: number,
  config: LaohuangStrategyConfig,
): boolean {
  return (
    !state.blacklisted &&
    nowMs - state.firstSeenAtMs <= config.trackWindowMs
  );
}

function matchesLaohuangStatus(
  state: LaohuangTokenState,
  status: DashboardFilters['strategyStatus'],
): boolean {
  if (status === 'all') {
    return true;
  }

  if (status === 'tracking') {
    return !state.dropTriggered && !state.reboundTriggered && !state.growthTriggered;
  }

  if (status === 'drop') {
    return state.dropTriggered;
  }

  if (status === 'rebound') {
    return state.reboundTriggered;
  }

  if (status === 'growth') {
    return state.growthTriggered;
  }

  return state.dropTriggered || state.reboundTriggered || state.growthTriggered;
}

function readLaohuangFdv(record: NotificationRecord): number | null {
  return (
    asOptionalNumber(record.context.dexscreener?.fdv) ??
    asOptionalNumber(record.context.dexscreener?.marketCap) ??
    asOptionalNumber(record.summary.marketCap)
  );
}

function getLaohuangChangePercent(
  state: LaohuangTokenState | null,
): number | null {
  if (!state || state.firstSeenFdv === null || state.firstSeenFdv <= 0) {
    return null;
  }

  if (state.currentFdv === null) {
    return null;
  }

  return ((state.currentFdv - state.firstSeenFdv) / state.firstSeenFdv) * 100;
}

function formatSignedPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return 'n/a';
  }

  return `${value > 0 ? '+' : ''}${value.toFixed(1)}%`;
}

function getLaohuangBadges(
  state: LaohuangTokenState | null,
): Array<{
  className?: string;
  label: string;
  variant: 'default' | 'secondary' | 'outline' | 'success';
}> {
  if (!state) {
    return [];
  }

  const badges: Array<{
    className?: string;
    label: string;
    variant: 'default' | 'secondary' | 'outline' | 'success';
  }> = [];

  if (state.reboundTriggered) {
    badges.push({
      className:
        'border border-amber-400/30 bg-[rgba(99,61,14,0.55)] text-amber-200 tracking-[0.12em]',
      label: 'rebound',
      variant: 'outline',
    });
  } else if (state.dropTriggered) {
    badges.push({
      className:
        'border border-red-400/30 bg-[rgba(87,21,29,0.56)] text-red-200 tracking-[0.12em]',
      label: 'drop',
      variant: 'outline',
    });
  }

  if (state.growthTriggered) {
    badges.push({
      className: 'tracking-[0.12em]',
      label: 'growth',
      variant: 'success',
    });
  }

  if (badges.length === 0) {
    badges.push({
      className: 'tracking-[0.12em]',
      label: 'tracking',
      variant: 'secondary',
    });
  }

  return badges;
}

function getLaohuangToneClass(
  state: LaohuangTokenState | null,
): string {
  if (!state) {
    return '';
  }

  if (state.reboundTriggered) {
    return 'bg-[linear-gradient(90deg,rgba(245,158,11,0.10),transparent_42%)]';
  }

  if (state.dropTriggered) {
    return 'bg-[linear-gradient(90deg,rgba(248,113,113,0.10),transparent_42%)]';
  }

  if (state.growthTriggered) {
    return 'bg-[linear-gradient(90deg,rgba(52,211,153,0.10),transparent_42%)]';
  }

  return '';
}

function normalizeStrategyValue(value: string | null | undefined): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
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

function formatUsd(value: number | null): string | null {
  if (value === null) {
    return null;
  }
  return `$${formatCompactNumber(value)}`;
}

function formatOptionalNumber(value: number | null): string | null {
  if (value === null) {
    return null;
  }
  return formatCompactNumber(value);
}

function formatLooseNumber(value: number | null): string | null {
  if (value === null) {
    return null;
  }
  return formatPlainMetric(value);
}

function formatPriceUsd(value: number | null): string | null {
  if (value === null) {
    return null;
  }

  if (value >= 1) {
    return `$${formatPlainNumber(Number(value.toFixed(4)))}`;
  }

  return `$${trimTrailingZeros(value.toFixed(10))}`;
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

function areStringArraysEqual(
  left: readonly string[],
  right: readonly string[],
): boolean {
  if (left.length !== right.length) {
    return false;
  }

  return left.every((value, index) => value === right[index]);
}

function padNumber(value: number): string {
  return value.toString().padStart(2, '0');
}

function truncateText(value: string, maxLength: number): string {
  if (value.length <= maxLength) {
    return value;
  }

  return `${value.slice(0, Math.max(0, maxLength - 1))}…`;
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

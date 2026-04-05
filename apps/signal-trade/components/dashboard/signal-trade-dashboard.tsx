'use client';

import type { JSX, ReactNode } from 'react';
import {
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
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
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  DEFAULT_DEX_WATCH_SUBSCRIPTIONS,
} from '@/lib/dexscreener-subscriptions';
import {
  applyStrategyPreset,
  isStrategyPresetEnabled,
  STRATEGY_PRESET_OPTIONS,
} from '@/lib/strategy-presets';
import {
  buildLaohuangConfig,
  buildLaohuangState,
  buildLatestLaohuangRecords,
  getLaohuangStateForRecord,
  isVisibleLaohuangState,
  matchesLaohuangStatus,
  type LaohuangTokenState,
  type LaohuangStrategyConfig,
} from '@/lib/laohuang-strategy';
import type {
  DashboardFilters,
  NotificationRecord,
  RuntimeDiagnosticsResult,
  WatchRuntimeState,
} from '@/lib/types';
import { cn } from '@/lib/utils';
import {
  areStringArraysEqual,
  asOptionalNumber,
  formatCompactNumber,
  formatCompactUnit,
  formatLooseNumber,
  formatOptionalNumber,
  formatPlainMetric,
  formatPlainNumber,
  formatPriceUsd,
  RELATIVE_TIME_TICK_MS,
  formatRelativeTime,
  formatUsd,
  padNumber,
  parseNumericFilter,
  trimTrailingZeros,
  truncateText,
} from '@/lib/format-utils';
import {
  ALL_DASHBOARD_CHAINS,
  areAllDashboardChainsSelected,
  matchesDashboardChainSelection,
} from '@/lib/dashboard-chain-filters';
import { matchesMarketCapRange } from '@/lib/dashboard-market-cap';
import {
  getSelectedWatchSubscriptions,
  mergeNotifications,
  parseListFilter,
  toggleWatchSubscription,
} from '@/lib/notification-utils';
import {
  buildNotificationPagination,
  buildPaginationItems,
  normalizePageSizeInput,
  NOTIFICATION_PAGE_SIZE_PRESETS,
} from '@/lib/dashboard-pagination';
import {
  formatDurationMs,
  formatWatchStatus,
  WATCH_LIMIT,
} from '@/lib/watch-utils';
import { useBrowserWatch } from '@/hooks/use-browser-watch';
import { useMarketDataEnrichment } from '@/hooks/use-market-data-enrichment';
import { useDiagnostics } from '@/hooks/use-diagnostics';
import { useSyncNotifications } from '@/hooks/use-sync-notifications';
import { NotificationListItem } from './notification-list-item';
import type { TokenMarketData } from './notification-list-item';
import {
  ControlMetricCard,
  ControlSection,
  DiagnosticsPanel,
  EmptyState,
  FieldGroup,
  RefreshChip,
  SelectField,
  SessionChip,
  SubscriptionMultiSelect,
  WatchChip,
  WatchStatusPanel,
} from './dashboard-widgets';
import { FilterDialog } from './filter-dialog';
import type { RefreshState } from './dashboard-widgets';

type DashboardProps = {
  initialFilters: DashboardFilters;
  initialNow: number;
  initialNotifications: NotificationRecord[];
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
    | 'minMarketCap'
    | 'minHolders'
    | 'paidOnly'
    | 'search'
    | 'strategyStatus'
    | 'watchSubscriptions'
    | 'watchTerms'
    | 'watchTransport';
  label: string;
};

const MAX_LAOHUANG_HISTORY = 1_000;
type NotificationPageSizeMode = `${(typeof NOTIFICATION_PAGE_SIZE_PRESETS)[number]}` | 'custom';

export function SignalTradeDashboard({
  initialFilters,
  initialNow,
  initialNotifications,
}: DashboardProps): JSX.Element {
  const [filters, setFilters] = useState<DashboardFilters>(initialFilters);
  const [pendingFilters, setPendingFilters] = useState<DashboardFilters>(initialFilters);
  const [notifications, setNotifications] =
    useState<NotificationRecord[]>(initialNotifications);
  const [laohuangHistory, setLaohuangHistory] = useState<NotificationRecord[]>(
    initialNotifications,
  );
  const [relativeNow, setRelativeNow] = useState(initialNow);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [requestedPage, setRequestedPage] = useState(1);
  const [pageSizeMode, setPageSizeMode] = useState<NotificationPageSizeMode>('10');
  const [customPageSizeInput, setCustomPageSizeInput] = useState('');

  const { watchRuntime, isWatchMutating, startWatch, stopWatch } = useBrowserWatch({
    onNotifications: (records) => {
      setLaohuangHistory(current => appendLaohuangHistory(current, records));
      setNotifications(current => mergeNotifications(current, records));
    },
  });
  const { isRefreshing, refreshState, refreshSummary, syncNotifications } = useSyncNotifications({
    onNotifications: appendNotifications,
    getSubscriptions: () => selectedWatchSubscriptions,
  });
  const { isDiagnosing, diagnostics, diagnosticsError, runDiagnostics } = useDiagnostics();
  const { marketDataVersion, getMarketData } = useMarketDataEnrichment(notifications);

  const deferredSearch = useDeferredValue(filters.search);
  const deferredWatchTerms = useDeferredValue(filters.watchTerms);

  useEffect(() => {
    setRelativeNow(Date.now());

    const timer = window.setInterval(() => {
      setRelativeNow(Date.now());
    }, RELATIVE_TIME_TICK_MS);

    return () => window.clearInterval(timer);
  }, []);

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
    if (!areAllDashboardChainsSelected(filters.chains)) {
      chips.push({
        id: 'chain',
        label: `链 ${filters.chains.join('/')}`,
      });
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
    if (filters.minMarketCap.trim()) {
      chips.push({
        id: 'minMarketCap',
        label: `市值 >= ${filters.minMarketCap.trim()}`,
      });
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
    if (isStrategyPresetEnabled(filters.strategyPreset) && filters.strategyStatus !== 'all') {
      chips.push({
        id: 'strategyStatus',
        label: `策略 ${filters.strategyStatus}`,
      });
    }

    return chips;
  }, [
    filters.chains,
    filters.maxHolders,
    filters.maxMarketCap,
    filters.minMarketCap,
    filters.minHolders,
    filters.paidOnly,
    filters.search,
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
    const minMarketCap = parseNumericFilter(filters.minMarketCap);
    const maxHolders = parseNumericFilter(filters.maxHolders);
    const maxMarketCap = parseNumericFilter(filters.maxMarketCap);
    const minCommunityCount = parseNumericFilter(filters.minCommunityCount);
    return strategyBaseRecords
      .filter(record => {
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
          ...(record.context.dexscreener?.websites ?? []),
          ...(record.context.dexscreener?.socials?.flatMap(social => [
            social.handle,
            social.platform,
            social.url,
          ]) ?? []),
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase();

        if (!matchesDashboardChainSelection(record.event.chain, filters.chains)) {
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
          !matchesMarketCapRange(record.summary.marketCap, {
            min: minMarketCap,
            max: maxMarketCap,
          })
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
    filters.chains,
    filters.maxMarketCap,
    filters.maxHolders,
    filters.minMarketCap,
    filters.minHolders,
    filters.paidOnly,
    filters.strategyPreset,
    filters.strategyStatus,
    laohuangConfig,
    laohuangStates,
    relativeNow,
    strategyBaseRecords,
  ]);

  const pageSize = useMemo(
    () =>
      pageSizeMode === 'custom'
        ? normalizePageSizeInput(customPageSizeInput)
        : Number.parseInt(pageSizeMode, 10),
    [customPageSizeInput, pageSizeMode],
  );
  const paginatedNotifications = useMemo(
    () =>
      buildNotificationPagination(filteredNotifications, {
        currentPage: requestedPage,
        pageSize,
      }),
    [filteredNotifications, pageSize, requestedPage],
  );
  const paginationItems = useMemo(
    () =>
      buildPaginationItems({
        currentPage: paginatedNotifications.currentPage,
        totalPages: paginatedNotifications.totalPages,
      }),
    [paginatedNotifications.currentPage, paginatedNotifications.totalPages],
  );
  const currentPageStart = paginatedNotifications.totalItems === 0
    ? 0
    : (paginatedNotifications.currentPage - 1) * paginatedNotifications.pageSize + 1;
  const currentPageEnd = paginatedNotifications.totalItems === 0
    ? 0
    : Math.min(
        paginatedNotifications.currentPage * paginatedNotifications.pageSize,
        paginatedNotifications.totalItems,
      );

  useEffect(() => {
    setRequestedPage(1);
  }, [
    deferredSearch,
    deferredWatchTerms,
    filters.chains,
    filters.maxHolders,
    filters.maxMarketCap,
    filters.minMarketCap,
    filters.minHolders,
    filters.paidOnly,
    filters.strategyPreset,
    filters.strategyStatus,
    pageSize,
  ]);

  useEffect(() => {
    if (requestedPage !== paginatedNotifications.currentPage) {
      setRequestedPage(paginatedNotifications.currentPage);
    }
  }, [paginatedNotifications.currentPage, requestedPage]);

  // Enrich notifications missing market data via DexScreener /tokens/v1 API


  function appendNotifications(nextNotifications: NotificationRecord[]): void {
    if (nextNotifications.length === 0) {
      return;
    }

    setLaohuangHistory(current =>
      appendLaohuangHistory(current, nextNotifications),
    );
    setNotifications(current => mergeNotifications(current, nextNotifications));
  }

  function updateFilter<Key extends keyof DashboardFilters>(
    key: Key,
    value: DashboardFilters[Key],
  ): void {
    setFilters(current => ({ ...current, [key]: value }));
  }

  function updatePendingFilter<Key extends keyof DashboardFilters>(
    key: Key,
    value: DashboardFilters[Key],
  ): void {
    setPendingFilters(current => ({ ...current, [key]: value }));
  }

  function applyPendingFilters(): void {
    setFilters(current => ({
      ...current,
      chains: pendingFilters.chains,
      paidOnly: pendingFilters.paidOnly,
      minHolders: pendingFilters.minHolders,
      minMarketCap: pendingFilters.minMarketCap,
      maxHolders: pendingFilters.maxHolders,
      maxMarketCap: pendingFilters.maxMarketCap,
    }));
  }

  function clearPendingFilters(): void {
    setPendingFilters(current => ({
      ...current,
      chains: initialFilters.chains,
      paidOnly: initialFilters.paidOnly,
      minHolders: initialFilters.minHolders,
      minMarketCap: initialFilters.minMarketCap,
      maxHolders: initialFilters.maxHolders,
      maxMarketCap: initialFilters.maxMarketCap,
    }));
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
      updateFilter('chains', [...ALL_DASHBOARD_CHAINS]);
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
    if (id === 'minMarketCap') {
      updateFilter('minMarketCap', '');
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
    Number(filters.paidOnly) +
    Number(!areAllDashboardChainsSelected(filters.chains)) +
    Number(filters.minHolders.trim().length > 0) +
    Number(filters.minMarketCap.trim().length > 0) +
    Number(filters.maxHolders.trim().length > 0) +
    Number(filters.maxMarketCap.trim().length > 0);

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(91,132,255,0.14),transparent_26%),radial-gradient(circle_at_top_right,rgba(168,85,247,0.08),transparent_20%),linear-gradient(180deg,rgba(255,255,255,0.015),rgba(255,255,255,0))]" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-24 bg-[linear-gradient(180deg,rgba(91,132,255,0.06),transparent)]" />

      <div className="relative mx-auto flex min-h-screen w-full max-w-[1580px] flex-col px-3 pb-8 pt-3 sm:px-4 lg:px-5 lg:pt-4">
        <div className="grid gap-4 xl:grid-cols-[280px_1fr]">
          <Card className="overflow-hidden xl:sticky xl:top-4 xl:self-start">
            <CardHeader className="border-b border-border/70 bg-[rgba(11,14,21,0.92)]">
              <div className="flex items-center justify-between gap-2">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Filter className="size-4 text-[color:var(--color-accent)]" />
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
                  onClick={() => { setPendingFilters(filters); setAdvancedOpen(true); }}
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
              <div className="mt-2 flex items-center gap-2">
                <Button
                  className="h-8 flex-1 rounded-full text-xs"
                  disabled={isRefreshing}
                  onClick={() => { void syncNotifications(); }}
                >
                  {isRefreshing ? (
                    <LoaderCircle className="size-3 animate-spin" />
                  ) : (
                    <RefreshCw className="size-3" />
                  )}
                  同步
                </Button>
                <WatchChip watchRuntime={watchRuntime} />
              </div>
              <div className="mt-3 grid gap-3">
                <FieldGroup label="快速搜索">
                  <div className="relative">
                    <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      className="pl-10"
                      placeholder="代币、合约、Twitter 用户名"
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
              </div>
            </CardHeader>
            <CardContent className="pt-4 space-y-4 overflow-y-auto max-h-[calc(100vh-12rem)]">
              <div className="grid grid-cols-2 gap-2">
                <Button
                  className="w-full rounded-full"
                  disabled={isWatchMutating}
                  variant="secondary"
                  onClick={() => { void startWatch(selectedWatchSubscriptions, filters.watchTransport); }}
                >
                  {watchRuntime?.running ? '重启' : '启动'}
                </Button>
                <Button
                  className="w-full rounded-full"
                  disabled={isWatchMutating || !watchRuntime?.running}
                  variant="outline"
                  onClick={() => { void stopWatch(selectedWatchSubscriptions, filters.watchTransport); }}
                >
                  停止
                </Button>
              </div>

              <div className="space-y-3">
                <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">监听配置</p>
                <FieldGroup label="观察名单关键词">
                  <Textarea
                    className="min-h-[60px] text-xs"
                    placeholder="支持逗号或换行，例如：ansem, base, hype"
                    value={filters.watchTerms}
                    onChange={event => updateFilter('watchTerms', event.target.value)}
                  />
                </FieldGroup>
                <div className="space-y-2">
                  <Label className="text-xs">WS 订阅</Label>
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
                </div>
              </div>



              <div className="space-y-2">
                <Button
                  className="w-full rounded-full"
                  disabled={isDiagnosing}
                  variant="outline"
                  onClick={() => { void runDiagnostics(); }}
                >
                  {isDiagnosing ? (
                    <LoaderCircle className="size-4 animate-spin" />
                  ) : (
                    <Target className="size-4" />
                  )}
                  诊断
                </Button>
                <DiagnosticsPanel
                  diagnostics={diagnostics}
                  diagnosticsError={diagnosticsError}
                />
              </div>
            </CardContent>
          </Card>

          <FilterDialog
            open={advancedOpen}
            onClose={() => setAdvancedOpen(false)}
            pendingFilters={pendingFilters}
            updatePendingFilter={updatePendingFilter}
            applyPendingFilters={applyPendingFilters}
            clearPendingFilters={clearPendingFilters}
          />

          <section className="overflow-hidden rounded-[24px] border border-border bg-[linear-gradient(180deg,rgba(10,12,19,0.98),rgba(8,10,16,0.98))] shadow-[0_18px_56px_rgba(0,0,0,0.24)]">
            <div className="border-b border-border/70 bg-[rgba(11,14,21,0.92)] px-5 py-4 sm:px-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 text-xl font-semibold text-foreground">
                    <Layers className="size-5 text-[color:var(--color-accent)]" />
                    扫链结果
                  </div>
                  {isStrategyPresetEnabled(filters.strategyPreset) ? (
                    <p className="mt-2 text-sm text-muted-foreground">
                      当前按 token 去重，并使用策略状态机过滤。
                    </p>
                  ) : null}
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
                <div className="space-y-4">
                  <div className="rounded-[20px] border border-border bg-[rgba(11,14,21,0.72)] p-3 sm:p-4">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
                      <div className="space-y-1">
                        <p className="text-sm font-medium text-foreground">
                          共 {paginatedNotifications.totalItems} 条结果
                        </p>
                        <p className="text-xs text-muted-foreground">
                          当前展示第 {currentPageStart}-{currentPageEnd} 条，按最新通知时间倒序排列
                        </p>
                      </div>
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                        <FieldGroup label="每页">
                          <div className="w-full min-w-[124px] sm:w-[124px]">
                            <SelectField
                              options={[
                                ...NOTIFICATION_PAGE_SIZE_PRESETS.map(value => ({
                                  label: `${value} 条`,
                                  value: String(value),
                                })),
                                { label: '自定义', value: 'custom' },
                              ]}
                              value={pageSizeMode}
                              onChange={value => {
                                setPageSizeMode(value as NotificationPageSizeMode);
                              }}
                            />
                          </div>
                        </FieldGroup>
                        {pageSizeMode === 'custom' ? (
                          <FieldGroup label="自定义">
                            <Input
                              className="w-full sm:w-[132px]"
                              inputMode="numeric"
                              min={1}
                              placeholder="输入页数"
                              type="number"
                              value={customPageSizeInput}
                              onChange={event => {
                                setCustomPageSizeInput(event.target.value);
                              }}
                            />
                          </FieldGroup>
                        ) : null}
                      </div>
                    </div>
                  </div>

                  <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                    {paginatedNotifications.items.map(record => (
                      <NotificationListItem
                        key={record.id}
                        currentTimeMs={relativeNow}
                        marketDataVersion={marketDataVersion}
                        enrichedMarketData={(() => {
                          const chain = record.event.chain ?? record.context.token?.chain ?? null;
                          const address = record.context.token?.address ?? record.event.token.address ?? null;
                          if (!chain || !address) return null;
                          return getMarketData(chain, address);
                        })()}
                        record={record}
                        strategyPreset={filters.strategyPreset}
                        strategyState={getLaohuangStateForRecord(laohuangStates, record)}
                      />
                    ))}
                  </ol>

                  <div className="flex flex-col gap-3 rounded-[20px] border border-border bg-[rgba(11,14,21,0.72)] p-3 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-xs text-muted-foreground">
                      第 {paginatedNotifications.currentPage} / {paginatedNotifications.totalPages} 页
                    </p>
                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={paginatedNotifications.currentPage <= 1}
                        onClick={() => { setRequestedPage(1); }}
                      >
                        首页
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={paginatedNotifications.currentPage <= 1}
                        onClick={() => {
                          setRequestedPage(paginatedNotifications.currentPage - 1);
                        }}
                      >
                        上一页
                      </Button>
                      {paginationItems.map(item =>
                        item.type === 'ellipsis' ? (
                          <span
                            key={item.id}
                            className="px-1 text-sm text-muted-foreground"
                          >
                            ...
                          </span>
                        ) : (
                          <Button
                            key={item.page}
                            size="sm"
                            variant={item.isCurrent ? 'default' : 'outline'}
                            onClick={() => { setRequestedPage(item.page); }}
                          >
                            {item.page}
                          </Button>
                        ),
                      )}
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={
                          paginatedNotifications.currentPage >=
                          paginatedNotifications.totalPages
                        }
                        onClick={() => {
                          setRequestedPage(paginatedNotifications.currentPage + 1);
                        }}
                      >
                        下一页
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={
                          paginatedNotifications.currentPage >=
                          paginatedNotifications.totalPages
                        }
                        onClick={() => {
                          setRequestedPage(paginatedNotifications.totalPages);
                        }}
                      >
                        尾页
                      </Button>
                    </div>
                  </div>
                </div>
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















function appendLaohuangHistory(
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
        new Date(left.notifiedAt).getTime() - new Date(right.notifiedAt).getTime(),
    )
    .slice(-MAX_LAOHUANG_HISTORY);
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

'use client';

import type { JSX, ReactNode } from 'react';
import {
  startTransition,
  useDeferredValue,
  useEffect,
  useMemo,
  useState,
} from 'react';
import type { LucideIcon } from 'lucide-react';
import {
  Activity,
  ArrowUpRight,
  BellRing,
  Coins,
  Filter,
  Flame,
  Layers,
  LoaderCircle,
  RefreshCw,
  Save,
  Search,
  Sparkles,
  Target,
  Users,
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
import { Separator } from '@/components/ui/separator';
import { Textarea } from '@/components/ui/textarea';
import type {
  DashboardFilters,
  NotificationRecord,
  StrategySnapshot,
} from '@/lib/types';
import { cn } from '@/lib/utils';

type DashboardProps = {
  initialFilters: DashboardFilters;
  initialNotifications: NotificationRecord[];
  strategies: StrategySnapshot[];
};

type SaveState = 'idle' | 'saving' | 'saved' | 'error';

export function SignalTradeDashboard({
  initialFilters,
  initialNotifications,
  strategies,
}: DashboardProps): JSX.Element {
  const [filters, setFilters] = useState<DashboardFilters>(initialFilters);
  const [notifications, setNotifications] =
    useState<NotificationRecord[]>(initialNotifications);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const deferredSearch = useDeferredValue(filters.search);
  const deferredWatchTerms = useDeferredValue(filters.watchTerms);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void refreshNotifications(false);
    }, 30_000);

    return () => window.clearInterval(timer);
  }, []);

  const chainOptions = useMemo(
    () =>
      uniqueValues([
        ...notifications.map(record => record.event.chain ?? ''),
        ...strategies.flatMap(strategy => strategy.chains),
      ]),
    [notifications, strategies],
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

  const strategyOptions = useMemo(
    () =>
      uniqueValues([
        ...notifications.map(record => record.strategyId),
        ...strategies.map(strategy => strategy.id),
      ]),
    [notifications, strategies],
  );

  const filteredNotifications = useMemo(() => {
    const search = deferredSearch.trim().toLowerCase();
    const watchTerms = parseWatchTerms(deferredWatchTerms);
    const minHolders = parseNumericFilter(filters.minHolders);
    const maxMarketCap = parseNumericFilter(filters.maxMarketCap);
    const minCommunityCount = parseNumericFilter(filters.minCommunityCount);

    return notifications.filter(record => {
      const sourceKey = `${record.event.source}.${record.event.subtype}`;
      const searchHaystack = [
        record.event.token.symbol,
        record.event.token.name,
        record.event.token.address,
        record.message,
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
      if (filters.strategyId !== 'all' && record.strategyId !== filters.strategyId) {
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
    });
  }, [
    deferredSearch,
    deferredWatchTerms,
    filters.chain,
    filters.maxMarketCap,
    filters.minCommunityCount,
    filters.minHolders,
    filters.paidOnly,
    filters.source,
    filters.strategyId,
    notifications,
  ]);

  const metrics = useMemo(() => {
    const paidCount = filteredNotifications.filter(item => item.summary.paid).length;
    const averageMarketCap = average(
      filteredNotifications
        .map(item => item.summary.marketCap)
        .filter((value): value is number => value !== null),
    );
    const topChain = topCount(
      filteredNotifications.map(item => item.event.chain || 'unknown'),
    );

    return {
      totalAlerts: notifications.length,
      visibleAlerts: filteredNotifications.length,
      paidRatio:
        filteredNotifications.length > 0
          ? Math.round((paidCount / filteredNotifications.length) * 100)
          : 0,
      averageMarketCap,
      topChain,
    };
  }, [filteredNotifications, notifications.length]);

  async function refreshNotifications(showSpinner: boolean): Promise<void> {
    if (showSpinner) {
      setIsRefreshing(true);
    }

    try {
      const response = await fetch('/api/notifications', {
        cache: 'no-store',
      });
      if (!response.ok) {
        throw new Error(`unexpected status ${response.status}`);
      }
      const payload = (await response.json()) as {
        notifications?: NotificationRecord[];
      };
      setNotifications(Array.isArray(payload.notifications) ? payload.notifications : []);
    } catch {
      // Keep current state when refresh fails.
    } finally {
      if (showSpinner) {
        setIsRefreshing(false);
      }
    }
  }

  function updateFilter<Key extends keyof DashboardFilters>(
    key: Key,
    value: DashboardFilters[Key],
  ): void {
    setFilters(current => ({ ...current, [key]: value }));
    if (saveState === 'saved') {
      setSaveState('idle');
    }
  }

  function resetFilters(): void {
    setFilters(initialFilters);
    setSaveState('idle');
  }

  function saveFilters(): void {
    startTransition(() => {
      void (async () => {
        setSaveState('saving');
        try {
          const response = await fetch('/api/dashboard-filters', {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(filters),
          });
          if (!response.ok) {
            throw new Error(`unexpected status ${response.status}`);
          }
          const payload = (await response.json()) as {
            filters?: DashboardFilters;
          };
          setFilters(payload.filters ?? filters);
          setSaveState('saved');
        } catch {
          setSaveState('error');
        }
      })();
    });
  }

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(0,162,142,0.14),transparent_28%),radial-gradient(circle_at_top_right,rgba(212,103,47,0.22),transparent_35%),linear-gradient(180deg,rgba(255,255,255,0.18),rgba(255,255,255,0))]" />

      <div className="relative mx-auto flex min-h-screen w-full max-w-[1560px] flex-col px-4 pb-10 pt-5 sm:px-6 lg:px-8">
        <header className="grid gap-6 rounded-[34px] border border-white/50 bg-white/72 px-5 py-6 shadow-[0_24px_90px_rgba(53,42,33,0.08)] backdrop-blur lg:grid-cols-[1.2fr_0.8fr] lg:px-8">
          <div className="space-y-5">
            <Badge className="w-fit gap-2 rounded-full px-3 py-1.5 text-[10px]">
              <Sparkles className="size-3" />
              Signal Trade Control Room
            </Badge>
            <div className="max-w-3xl space-y-3">
              <h1 className="text-4xl font-semibold tracking-[-0.05em] text-balance text-foreground sm:text-5xl">
                把 Python 信号流转成一块可交互的全栈筛选面板
              </h1>
              <p className="max-w-2xl text-sm leading-7 text-muted-foreground sm:text-base">
                Next.js 负责数据面板、过滤条件和策略摘要，Python 继续做
                DexScreener / X / XXYY 采集与命中通知。前端会轮询本地通知存储，
                用同一套界面看热度、看链路、看命中代币。
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button
                className="rounded-full"
                onClick={() => {
                  void refreshNotifications(true);
                }}
              >
                {isRefreshing ? (
                  <LoaderCircle className="size-4 animate-spin" />
                ) : (
                  <RefreshCw className="size-4" />
                )}
                刷新通知
              </Button>
              <Button className="rounded-full" variant="secondary" onClick={saveFilters}>
                <Save className="size-4" />
                保存筛选条件
              </Button>
              <StatusChip saveState={saveState} />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <MetricCard
              hint="累计可视通知"
              icon={BellRing}
              label="Visible Alerts"
              value={String(metrics.visibleAlerts)}
            />
            <MetricCard
              hint="当前筛选结果中 paid 比例"
              icon={Activity}
              label="Paid Coverage"
              value={`${metrics.paidRatio}%`}
            />
            <MetricCard
              hint="当前筛选结果中的平均市值"
              icon={Coins}
              label="Avg Market Cap"
              value={formatUsd(metrics.averageMarketCap)}
            />
            <MetricCard
              hint="最活跃链路"
              icon={Flame}
              label="Top Chain"
              value={metrics.topChain}
            />
          </div>
        </header>

        <div className="mt-6 grid gap-6 xl:grid-cols-[340px_minmax(0,1fr)]">
          <aside className="space-y-6 xl:sticky xl:top-6 xl:self-start">
            <Card className="overflow-hidden">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-xl">
                  <Filter className="size-5 text-[color:var(--color-accent)]" />
                  Dashboard Filters
                </CardTitle>
                <CardDescription>
                  前端保存的筛选条件只影响展示层，不会改写 Python 采集逻辑。
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <FieldGroup label="快速搜索">
                  <div className="relative">
                    <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      className="pl-10"
                      placeholder="代币、策略、Twitter 用户名"
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
                  <FieldGroup label="策略">
                    <SelectField
                      options={['all', ...strategyOptions]}
                      value={filters.strategyId}
                      onChange={value => updateFilter('strategyId', value)}
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
                  <Button className="flex-1 rounded-full" onClick={saveFilters}>
                    <Save className="size-4" />
                    保存
                  </Button>
                  <Button className="rounded-full" variant="outline" onClick={resetFilters}>
                    重置
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-xl">
                  <Target className="size-5 text-[color:var(--color-accent)]" />
                  Strategy Snapshot
                </CardTitle>
                <CardDescription>
                  从 `rules.json` 读取的当前策略摘要，方便对照前端筛选结果。
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {strategies.map(strategy => (
                  <StrategyCard key={strategy.id} strategy={strategy} />
                ))}
              </CardContent>
            </Card>
          </aside>

          <section className="space-y-6">
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
              <Card className="overflow-hidden">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-xl">
                    <Layers className="size-5 text-[color:var(--color-accent)]" />
                    Notification Stream
                  </CardTitle>
                  <CardDescription>
                    当前后端累计记录 {metrics.totalAlerts} 条通知，筛选后显示{' '}
                    {metrics.visibleAlerts} 条。
                  </CardDescription>
                </CardHeader>
                <CardContent className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
                  {filteredNotifications.length > 0 ? (
                    filteredNotifications.map(record => (
                      <NotificationCard key={record.id} record={record} />
                    ))
                  ) : (
                    <EmptyState />
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-xl">
                    <Users className="size-5 text-[color:var(--color-accent)]" />
                    Operator Notes
                  </CardTitle>
                  <CardDescription>
                    这里是前端最适合快速判断的几个信号切片。
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <FocusRow
                    label="优先查看"
                    value={
                      filters.search ||
                      filters.watchTerms ||
                      (filters.strategyId !== 'all' ? filters.strategyId : '全部信号')
                    }
                  />
                  <FocusRow
                    label="筛选阈值"
                    value={[
                      filters.minHolders && `holders ≥ ${filters.minHolders}`,
                      filters.maxMarketCap && `market cap ≤ ${filters.maxMarketCap}`,
                      filters.minCommunityCount &&
                        `community ≥ ${filters.minCommunityCount}`,
                    ]
                      .filter(Boolean)
                      .join(' · ') || '未设置'}
                  />
                  <Separator />
                  {filteredNotifications.slice(0, 3).map(record => (
                    <div
                      key={record.id}
                      className="rounded-3xl border border-border bg-[color:var(--color-panel-soft)] p-4"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-foreground">
                            {record.event.token.symbol || 'UNKNOWN'}
                          </p>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {record.event.token.name || record.event.token.address}
                          </p>
                        </div>
                        <Badge variant={record.summary.paid ? 'success' : 'secondary'}>
                          {record.summary.paid ? 'paid' : 'organic'}
                        </Badge>
                      </div>
                      <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
                        <span>{record.strategyId}</span>
                        <span>{formatRelativeTime(record.notifiedAt)}</span>
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function MetricCard({
  hint,
  icon: Icon,
  label,
  value,
}: {
  hint: string;
  icon: LucideIcon;
  label: string;
  value: string;
}): JSX.Element {
  return (
    <Card className="border-white/60 bg-[linear-gradient(180deg,rgba(255,255,255,0.9),rgba(250,244,238,0.92))]">
      <CardContent className="flex h-full flex-col justify-between gap-4 p-5">
        <div className="flex items-center justify-between">
          <Badge variant="secondary">{label}</Badge>
          <div className="rounded-2xl bg-[color:var(--color-panel-soft)] p-2 text-[color:var(--color-accent)]">
            <Icon className="size-4" />
          </div>
        </div>
        <div>
          <p className="text-3xl font-semibold tracking-[-0.04em] text-foreground">
            {value}
          </p>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">{hint}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function StatusChip({ saveState }: { saveState: SaveState }): JSX.Element {
  if (saveState === 'saving') {
    return (
      <Badge variant="secondary" className="gap-2 px-3 py-1.5 normal-case tracking-normal">
        <LoaderCircle className="size-3 animate-spin" />
        正在保存筛选条件
      </Badge>
    );
  }
  if (saveState === 'saved') {
    return (
      <Badge variant="success" className="px-3 py-1.5 normal-case tracking-normal">
        已保存到 data/dashboard-filters.json
      </Badge>
    );
  }
  if (saveState === 'error') {
    return (
      <Badge className="px-3 py-1.5 normal-case tracking-normal" variant="outline">
        保存失败，请检查本地写入权限
      </Badge>
    );
  }
  return (
    <Badge variant="secondary" className="px-3 py-1.5 normal-case tracking-normal">
      前端筛选条件未保存
    </Badge>
  );
}

function StrategyCard({
  strategy,
}: {
  strategy: StrategySnapshot;
}): JSX.Element {
  return (
    <div className="rounded-[28px] border border-border bg-[color:var(--color-panel-soft)] p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-foreground">{strategy.id}</p>
          <p className="mt-1 text-xs text-muted-foreground">{strategy.source}</p>
        </div>
        <Badge variant={strategy.enabled ? 'success' : 'outline'}>
          {strategy.enabled ? 'enabled' : 'disabled'}
        </Badge>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {strategy.chains.map(chain => (
          <Badge key={chain} variant="secondary">
            {chain}
          </Badge>
        ))}
        {strategy.channels.map(channel => (
          <Badge key={channel} variant="outline">
            {channel}
          </Badge>
        ))}
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
        <SummaryItem label="Min holders" value={formatOptionalNumber(strategy.minHolderCount)} />
        <SummaryItem label="Max holders" value={formatOptionalNumber(strategy.maxHolderCount)} />
        <SummaryItem label="Max market cap" value={formatUsd(strategy.maxMarketCap)} />
        <SummaryItem label="Tracked KOL" value={String(strategy.trackedKolNames.length)} />
      </dl>
      {(strategy.trackedKolNames.length > 0 ||
        strategy.trackedFollowAddresses.length > 0) && (
        <>
          <Separator className="my-4" />
          <div className="space-y-3 text-xs text-muted-foreground">
            {strategy.trackedKolNames.length > 0 && (
              <p>
                <span className="font-semibold text-foreground">KOL</span>{' '}
                {strategy.trackedKolNames.join(', ')}
              </p>
            )}
            {strategy.trackedFollowAddresses.length > 0 && (
              <p className="break-all">
                <span className="font-semibold text-foreground">Follow wallets</span>{' '}
                {strategy.trackedFollowAddresses.join(', ')}
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function NotificationCard({
  record,
}: {
  record: NotificationRecord;
}): JSX.Element {
  const sourceKey = `${record.event.source}.${record.event.subtype}`;

  return (
    <article className="group flex h-full flex-col rounded-[30px] border border-border bg-[linear-gradient(180deg,rgba(255,255,255,0.95),rgba(248,242,235,0.94))] p-5 shadow-[0_18px_55px_rgba(22,20,18,0.06)] transition-transform duration-200 hover:-translate-y-1">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-xl font-semibold tracking-[-0.04em] text-foreground">
              {record.event.token.symbol || 'UNKNOWN'}
            </p>
            <Badge variant={record.summary.paid ? 'success' : 'secondary'}>
              {record.summary.paid ? 'paid' : 'organic'}
            </Badge>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {record.event.token.name || record.event.token.address || 'unnamed token'}
          </p>
        </div>
        <span className="rounded-full bg-[color:var(--color-panel-soft)] px-3 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          {record.event.chain || 'n/a'}
        </span>
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        <InfoPill icon={Layers} label={record.strategyId} />
        <InfoPill icon={Activity} label={sourceKey} />
        <InfoPill icon={BellRing} label={record.channels.join(', ') || 'stdout'} />
      </div>

      <dl className="mt-5 grid grid-cols-2 gap-3">
        <SignalStat
          icon={Coins}
          label="市值"
          value={formatUsd(record.summary.marketCap)}
        />
        <SignalStat
          icon={Users}
          label="持币人数"
          value={formatOptionalNumber(record.summary.holderCount)}
        />
        <SignalStat
          icon={Sparkles}
          label="社区人数"
          value={formatOptionalNumber(record.summary.communityCount)}
        />
        <SignalStat
          icon={Flame}
          label="关注者"
          value={formatOptionalNumber(record.summary.followersCount)}
        />
      </dl>

      <p className="mt-5 line-clamp-3 text-sm leading-6 text-muted-foreground">
        {record.message}
      </p>

      <div className="mt-5 flex flex-wrap gap-2">
        {record.summary.twitterUsername ? (
          <a
            className="inline-flex items-center gap-1 rounded-full border border-border px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-[color:var(--color-panel-soft)]"
            href={`https://x.com/${record.summary.twitterUsername}`}
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

      <div className="mt-auto pt-6 text-xs text-muted-foreground">
        <span className="font-mono">{formatRelativeTime(record.notifiedAt)}</span>
      </div>
    </article>
  );
}

function EmptyState(): JSX.Element {
  return (
    <div className="md:col-span-2 2xl:col-span-3">
      <div className="flex min-h-[280px] flex-col items-center justify-center rounded-[32px] border border-dashed border-border bg-[color:var(--color-panel-soft)] px-6 py-10 text-center">
        <div className="rounded-full bg-[color:var(--color-accent)]/10 p-4 text-[color:var(--color-accent)]">
          <BellRing className="size-8" />
        </div>
        <h3 className="mt-5 text-2xl font-semibold tracking-[-0.04em] text-foreground">
          当前没有命中的通知代币
        </h3>
        <p className="mt-3 max-w-md text-sm leading-6 text-muted-foreground">
          你可以降低前端筛选阈值，或者先运行 Python 后端采集命令，把新的通知记录写入
          `data/notifications.json`。
        </p>
      </div>
    </div>
  );
}

function SignalStat({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
}): JSX.Element {
  return (
    <div className="rounded-3xl border border-border bg-white/80 p-3">
      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">
        <Icon className="size-3.5" />
        {label}
      </div>
      <p className="mt-2 text-sm font-semibold text-foreground">{value}</p>
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

function SummaryItem({
  label,
  value,
}: {
  label: string;
  value: string;
}): JSX.Element {
  return (
    <div className="rounded-2xl border border-border bg-white/80 p-3">
      <dt className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-2 text-sm font-semibold text-foreground">{value}</dd>
    </div>
  );
}

function FocusRow({
  label,
  value,
}: {
  label: string;
  value: string;
}): JSX.Element {
  return (
    <div className="rounded-3xl border border-border bg-[color:var(--color-panel-soft)] p-4">
      <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-2 text-sm font-semibold leading-6 text-foreground">{value}</p>
    </div>
  );
}

function uniqueValues(values: string[]): string[] {
  return Array.from(
    new Set(values.map(item => item.trim()).filter(Boolean)),
  ).sort((left, right) => left.localeCompare(right));
}

function parseWatchTerms(value: string): string[] {
  return value
    .split(/[\n,]/)
    .map(item => item.trim().toLowerCase())
    .filter(Boolean);
}

function parseNumericFilter(value: string): number | null {
  if (!value.trim()) {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function average(values: number[]): number | null {
  if (values.length === 0) {
    return null;
  }
  const total = values.reduce((sum, value) => sum + value, 0);
  return total / values.length;
}

function topCount(values: string[]): string {
  const counter = new Map<string, number>();
  for (const value of values) {
    counter.set(value, (counter.get(value) ?? 0) + 1);
  }
  const top = Array.from(counter.entries()).sort((left, right) => right[1] - left[1])[0];
  return top ? top[0] : 'n/a';
}

function formatUsd(value: number | null): string {
  if (value === null) {
    return 'N/A';
  }
  return new Intl.NumberFormat('en-US', {
    notation: 'compact',
    maximumFractionDigits: value >= 1_000_000 ? 2 : 1,
    style: 'currency',
    currency: 'USD',
  }).format(value);
}

function formatOptionalNumber(value: number | null): string {
  if (value === null) {
    return 'N/A';
  }
  return new Intl.NumberFormat('en-US', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value);
}

function formatRelativeTime(value: string): string {
  const date = new Date(value);
  const diffMs = date.getTime() - Date.now();
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

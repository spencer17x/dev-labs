'use client';

import type { JSX, ReactNode } from 'react';
import { LoaderCircle, Target } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  BellRing,
} from 'lucide-react';
import {
  DEX_WATCH_SUBSCRIPTION_OPTIONS,
} from '@/lib/dexscreener-subscriptions';
import type { RuntimeDiagnosticsResult, WatchRuntimeState } from '@/lib/types';
import { cn } from '@/lib/utils';
import {
  formatAbsoluteTime,
  formatNetworkCheck,
  formatNotificationStore,
  formatWatchStatus,
  formatWatchSubscriptions,
  hasWatchConnectionIssue,
} from '@/lib/watch-utils';

export type RefreshState = 'idle' | 'syncing' | 'synced' | 'error';

export function SessionChip(): JSX.Element {
  return (
    <Badge
      variant="secondary"
      className="border border-border px-3 py-1.5 normal-case tracking-normal"
    >
      仅当前页面会话
    </Badge>
  );
}

export function RefreshChip({
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

export function WatchChip({
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

export function ControlMetricCard({
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

export function WatchStatusPanel({
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

export function DiagnosticsPanel({
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

export function EmptyState({
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

export function FieldGroup({
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

export function ControlSection({
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

export function SelectField({
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

export function SubscriptionMultiSelect({
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

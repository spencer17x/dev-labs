'use client';

import type { JSX } from 'react';
import { Badge } from '@/components/ui/badge';
import { Dialog } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import {
  applyStrategyPreset,
  STRATEGY_PRESET_OPTIONS,
} from '@/lib/strategy-presets';
import type { DashboardFilters } from '@/lib/types';
import { cn } from '@/lib/utils';

import { FieldGroup, SelectField } from './dashboard-widgets';

interface FilterDialogProps {
  open: boolean;
  onClose: () => void;
  pendingFilters: DashboardFilters;
  setPendingFilters: React.Dispatch<React.SetStateAction<DashboardFilters>>;
  updatePendingFilter: <Key extends keyof DashboardFilters>(key: Key, value: DashboardFilters[Key]) => void;
  updatePendingStrategyFilter: <Key extends keyof DashboardFilters>(key: Key, value: DashboardFilters[Key]) => void;
  applyPendingFilters: () => void;
  clearPendingFilters: () => void;
  chainOptions: string[];
  sourceOptions: string[];
}

export function FilterDialog({
  open,
  onClose,
  pendingFilters,
  setPendingFilters,
  updatePendingFilter,
  updatePendingStrategyFilter,
  applyPendingFilters,
  clearPendingFilters,
  chainOptions,
  sourceOptions,
}: FilterDialogProps): JSX.Element {
  return (
    <Dialog open={open} title="筛选设置" onClose={onClose}>
      <div className="space-y-4 overflow-y-auto max-h-[60vh]">
        {/* 链路 + 来源 */}
        <div className="grid gap-3 sm:grid-cols-2">
          <FieldGroup label="链路">
            <SelectField
              options={['all', ...chainOptions]}
              value={pendingFilters.chain}
              onChange={value => updatePendingFilter('chain', value)}
            />
          </FieldGroup>
          <FieldGroup label="来源">
            <SelectField
              options={['all', ...sourceOptions]}
              value={pendingFilters.source}
              onChange={value => updatePendingFilter('source', value)}
            />
          </FieldGroup>
        </div>

        {/* 持币 + 市值 */}
        <div className="grid gap-3 sm:grid-cols-2">
          <FieldGroup label="最少持币人数">
            <Input
              inputMode="numeric"
              placeholder="100"
              value={pendingFilters.minHolders}
              onChange={event => updatePendingFilter('minHolders', event.target.value)}
            />
          </FieldGroup>
          <FieldGroup label="最多持币人数">
            <Input
              inputMode="numeric"
              placeholder="5000"
              value={pendingFilters.maxHolders}
              onChange={event => updatePendingFilter('maxHolders', event.target.value)}
            />
          </FieldGroup>
          <FieldGroup label="最高市值">
            <Input
              inputMode="numeric"
              placeholder="3000000"
              value={pendingFilters.maxMarketCap}
              onChange={event => updatePendingFilter('maxMarketCap', event.target.value)}
            />
          </FieldGroup>
        </div>

        {/* 策略预设 */}
        <FieldGroup label="策略预设">
          <SelectField
            options={STRATEGY_PRESET_OPTIONS.map(option => ({
              label: option.label,
              value: option.value,
            }))}
            value={pendingFilters.strategyPreset}
            onChange={value =>
              setPendingFilters(current =>
                applyStrategyPreset(current, value as DashboardFilters['strategyPreset']),
              )
            }
          />
        </FieldGroup>

        {/* 策略详细参数 */}
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <FieldGroup label="首推 FDV 上限">
              <Input
                inputMode="decimal"
                placeholder="80000"
                value={pendingFilters.strategyMaxFirstSeenFdv}
                onChange={event => updatePendingStrategyFilter('strategyMaxFirstSeenFdv', event.target.value)}
              />
            </FieldGroup>
            <FieldGroup label="跟踪窗口(h)">
              <Input
                inputMode="decimal"
                placeholder="12"
                value={pendingFilters.strategyTrackHours}
                onChange={event => updatePendingStrategyFilter('strategyTrackHours', event.target.value)}
              />
            </FieldGroup>
            <FieldGroup label="下跌比例">
              <Input
                inputMode="decimal"
                placeholder="0.5"
                value={pendingFilters.strategyDropRatio}
                onChange={event => updatePendingStrategyFilter('strategyDropRatio', event.target.value)}
              />
            </FieldGroup>
            <FieldGroup label="回调倍数">
              <Input
                inputMode="decimal"
                placeholder="1.2"
                value={pendingFilters.strategyReboundRatio}
                onChange={event => updatePendingStrategyFilter('strategyReboundRatio', event.target.value)}
              />
            </FieldGroup>
            <FieldGroup label="回调延迟(s)">
              <Input
                inputMode="decimal"
                placeholder="6"
                value={pendingFilters.strategyReboundDelaySec}
                onChange={event => updatePendingStrategyFilter('strategyReboundDelaySec', event.target.value)}
              />
            </FieldGroup>
            <FieldGroup label="涨幅阈值 %">
              <Input
                inputMode="decimal"
                placeholder="20"
                value={pendingFilters.strategyGrowthPercent}
                onChange={event => updatePendingStrategyFilter('strategyGrowthPercent', event.target.value)}
              />
            </FieldGroup>
          </div>
          <button
            type="button"
            className={cn(
              'flex w-full items-center justify-between rounded-[14px] border px-3 py-2.5 text-left transition-colors',
              pendingFilters.strategyRequirePaid
                ? 'border-[color:var(--color-accent)] bg-[rgba(91,132,255,0.12)]'
                : 'border-border bg-[color:var(--color-panel-soft)]',
            )}
            onClick={() => updatePendingStrategyFilter('strategyRequirePaid', !pendingFilters.strategyRequirePaid)}
          >
            <p className="text-xs font-semibold text-foreground">种子必须是 Paid</p>
            <Badge variant={pendingFilters.strategyRequirePaid ? 'success' : 'secondary'}>
              {pendingFilters.strategyRequirePaid ? 'ON' : 'OFF'}
            </Badge>
          </button>
        </div>

        {/* 仅看 Paid */}
        <button
          type="button"
          className={cn(
            'flex w-full items-center justify-between rounded-[18px] border px-4 py-3 text-left transition-colors',
            pendingFilters.paidOnly
              ? 'border-[color:var(--color-accent)] bg-[rgba(91,132,255,0.12)] shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]'
              : 'border-border bg-[color:var(--color-panel-soft)]',
          )}
          onClick={() => updatePendingFilter('paidOnly', !pendingFilters.paidOnly)}
        >
          <div>
            <p className="text-sm font-semibold text-foreground">仅看 Paid Dex 通知</p>
            <p className="text-xs text-muted-foreground">对应 `dexscreener.paid = true`</p>
          </div>
          <Badge variant={pendingFilters.paidOnly ? 'success' : 'secondary'}>
            {pendingFilters.paidOnly ? 'ON' : 'OFF'}
          </Badge>
        </button>
      </div>

      {/* Footer */}
      <div className="mt-6 flex items-center justify-end gap-3 border-t border-border/60 pt-4">
        <button
          type="button"
          className="rounded-full border border-border bg-[rgba(14,18,27,0.92)] px-4 py-2 text-xs font-semibold text-muted-foreground transition-colors hover:text-foreground"
          onClick={clearPendingFilters}
        >
          清空筛选
        </button>
        <button
          type="button"
          className="rounded-full bg-[color:var(--color-accent)] px-5 py-2 text-xs font-semibold text-white shadow-[0_0_12px_rgba(91,132,255,0.35)] transition-opacity hover:opacity-90"
          onClick={() => { applyPendingFilters(); onClose(); }}
        >
          确认
        </button>
      </div>
    </Dialog>
  );
}

import type { DashboardFilters, StrategyPreset } from '@/lib/types';

type StrategyConfigKeys =
  | 'strategySeedSubscription'
  | 'strategySeedChain'
  | 'strategyRequirePaid'
  | 'strategyMaxFirstSeenFdv'
  | 'strategyDropRatio'
  | 'strategyReboundRatio'
  | 'strategyReboundDelaySec'
  | 'strategyGrowthPercent'
  | 'strategyTrackHours';

export type StrategyPresetConfig = Pick<DashboardFilters, StrategyConfigKeys>;
export type StrategyPresetOption = {
  description: string;
  label: string;
  value: StrategyPreset;
};

const STRATEGY_PRESET_CONFIGS: Record<
  Exclude<StrategyPreset, 'none' | 'custom'>,
  StrategyPresetConfig
> = {
  laohuang: {
    strategySeedSubscription: 'token_profiles_latest',
    strategySeedChain: 'solana',
    strategyRequirePaid: true,
    strategyMaxFirstSeenFdv: '80000',
    strategyDropRatio: '0.5',
    strategyReboundRatio: '1.2',
    strategyReboundDelaySec: '6',
    strategyGrowthPercent: '20',
    strategyTrackHours: '12',
  },
};

export const STRATEGY_PRESET_OPTIONS: StrategyPresetOption[] = [
  {
    value: 'none',
    label: '关闭',
    description: '不启用策略状态机，只看普通通知流。',
  },
  {
    value: 'laohuang',
    label: 'laohuang',
    description: '之前梳理出来的 laohuang 预设规则。',
  },
  {
    value: 'custom',
    label: '自定义',
    description: '保留当前输入参数，不套用模板。',
  },
];

export function normalizeStrategyPreset(
  value: string | null | undefined,
): StrategyPreset {
  if (
    value === 'laohuang' ||
    value === 'solana_paid_seed_reversal' ||
    value === 'solana_paid_seed_reversal_strict' ||
    value === 'solana_paid_seed_reversal_loose'
  ) {
    return 'laohuang';
  }

  return STRATEGY_PRESET_OPTIONS.some(option => option.value === value)
    ? (value as StrategyPreset)
    : 'none';
}

export function applyStrategyPreset(
  filters: DashboardFilters,
  preset: StrategyPreset,
): DashboardFilters {
  if (preset === 'none' || preset === 'custom') {
    return {
      ...filters,
      strategyPreset: preset,
    };
  }

  return {
    ...filters,
    strategyPreset: preset,
    ...STRATEGY_PRESET_CONFIGS[preset],
  };
}

export function getStrategyPresetConfig(
  preset: StrategyPreset,
): StrategyPresetConfig | null {
  if (preset === 'none' || preset === 'custom') {
    return null;
  }

  return STRATEGY_PRESET_CONFIGS[preset];
}

export function getStrategyPresetDescription(
  preset: StrategyPreset,
): string | null {
  return (
    STRATEGY_PRESET_OPTIONS.find(option => option.value === preset)?.description ?? null
  );
}

export function isStrategyPresetEnabled(
  preset: StrategyPreset,
): boolean {
  return preset !== 'none';
}

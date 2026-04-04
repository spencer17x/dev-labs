export type LaohuangStage = 'tracking' | 'dropped' | 'rebounded';

export type LaohuangTokenState = {
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

export type LaohuangStrategyConfig = {
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

export type DashboardFiltersLike = {
  strategyDropRatio: string;
  strategyGrowthPercent: string;
  strategyMaxFirstSeenFdv: string;
  strategyReboundDelaySec: string;
  strategyReboundRatio: string;
  strategyRequirePaid: boolean;
  strategySeedChain: string;
  strategySeedSubscription: string;
  strategyTrackHours: string;
};

export type StrategyStatusLike =
  | 'all'
  | 'tracking'
  | 'drop'
  | 'rebound'
  | 'growth'
  | 'triggered';

type NotificationRecordLike = {
  notifiedAt: string;
  event: {
    chain?: string | null;
    source: string;
    subtype: string;
    token: {
      address?: string | null;
    };
  };
  context: {
    token?: {
      address?: string | null;
    };
    dexscreener?: {
      fdv?: number | string | null;
      marketCap?: number | string | null;
      priceUsd?: number | string | null;
    };
  };
  summary: {
    marketCap: number | null;
    paid: boolean;
    priceUsd: number | null;
  };
};

const LAOHUANG_MAX_FIRST_SEEN_FDV = 80_000;
const LAOHUANG_DROP_RATIO = 0.5;
const LAOHUANG_REBOUND_RATIO = 1.2;
const LAOHUANG_REBOUND_DELAY_MS = 6_000;
const LAOHUANG_GROWTH_PERCENT = 20;
const LAOHUANG_MAX_TRACK_MS = 12 * 60 * 60 * 1000;
const LAOHUANG_SOURCE_KEY = 'dexscreener.token_profiles_latest';

export function buildLaohuangConfig(
  filters: DashboardFiltersLike,
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

export function buildLaohuangState(
  records: NotificationRecordLike[],
  config: LaohuangStrategyConfig,
): Record<string, LaohuangTokenState> {
  return reduceLaohuangState({}, records, config);
}

export function buildLatestLaohuangRecords<T extends NotificationRecordLike>(
  notifications: T[],
  states: Record<string, LaohuangTokenState>,
): T[] {
  const latestByToken = new Map<string, T>();

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

export function getLaohuangStateForRecord(
  states: Record<string, LaohuangTokenState>,
  record: NotificationRecordLike,
): LaohuangTokenState | null {
  const tokenKey = getNotificationTokenKey(record);
  if (!tokenKey) {
    return null;
  }

  return states[tokenKey] ?? null;
}

export function getNotificationTokenKey(
  record: NotificationRecordLike,
): string | null {
  const chain = normalizeStrategyValue(record.event.chain)?.toLowerCase();
  const address =
    normalizeStrategyValue(record.context.token?.address) ??
    normalizeStrategyValue(record.event.token.address);

  if (!chain || !address) {
    return null;
  }

  return `${chain}:${address.toLowerCase()}`;
}

export function isVisibleLaohuangState(
  state: LaohuangTokenState,
  nowMs: number,
  config: LaohuangStrategyConfig,
): boolean {
  return (
    !state.blacklisted &&
    nowMs - state.firstSeenAtMs <= config.trackWindowMs
  );
}

export function matchesLaohuangStatus(
  state: LaohuangTokenState,
  status: StrategyStatusLike,
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

export function readLaohuangFdv(
  record: NotificationRecordLike,
): number | null {
  return asOptionalNumber(record.context.dexscreener?.fdv);
}

function reduceLaohuangState(
  current: Record<string, LaohuangTokenState>,
  incoming: NotificationRecordLike[],
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

function isLaohuangSeedRecord(
  record: NotificationRecordLike,
  config: LaohuangStrategyConfig,
): boolean {
  const chain = normalizeStrategyValue(record.event.chain)?.toLowerCase();
  return (
    chain === config.chain &&
    `${record.event.source}.${record.event.subtype}` === config.seedSourceKey &&
    (!config.requirePaid || record.summary.paid)
  );
}

function parseNumericFilter(value: string): number | null {
  if (!value.trim()) {
    return null;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
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

function normalizeStrategyValue(value: string | null | undefined): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

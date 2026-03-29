import fs from 'node:fs';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

import { defaultDashboardFilters, demoNotifications } from '@/lib/demo-data';
import type {
  DashboardFilters,
  NotificationRecord,
  SignalContext,
  SignalEvent,
  StrategySnapshot,
} from '@/lib/types';

const APP_DIR = resolveAppDir();
const DATA_DIR = path.join(APP_DIR, 'data');
const NOTIFICATIONS_FILE = path.join(DATA_DIR, 'notifications.json');
const DASHBOARD_FILTERS_FILE = path.join(DATA_DIR, 'dashboard-filters.json');
const RULES_FILE = path.join(APP_DIR, 'rules.json');

type JsonObject = Record<string, unknown>;

type RawRuleCondition = {
  field?: string;
  op?: string;
  value?: unknown;
  logic?: string;
  conditions?: RawRuleCondition[];
};

type RawRuleStrategy = {
  id?: string;
  enabled?: boolean;
  chains?: unknown;
  source?: unknown;
  notify?: unknown;
  action?: { channels?: unknown };
  entry_conditions?: RawRuleCondition[];
  reject_conditions?: RawRuleCondition[];
  entry_rule?: RawRuleCondition;
  reject_rule?: RawRuleCondition;
};

function resolveAppDir(): string {
  const candidates = [
    process.cwd(),
    path.join(process.cwd(), 'apps', 'signal-trade'),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(path.join(candidate, 'rules.json'))) {
      return candidate;
    }
  }
  return candidates[0];
}

export function normalizeDashboardFilters(
  value: Partial<DashboardFilters> | Record<string, unknown> | null | undefined,
): DashboardFilters {
  return {
    search: readString(value, 'search'),
    watchTerms: readString(value, 'watchTerms'),
    chain: readString(value, 'chain') || 'all',
    source: readString(value, 'source') || 'all',
    strategyId: readString(value, 'strategyId') || 'all',
    minHolders: sanitizeNumericInput(readString(value, 'minHolders')),
    maxMarketCap: sanitizeNumericInput(readString(value, 'maxMarketCap')),
    minCommunityCount: sanitizeNumericInput(readString(value, 'minCommunityCount')),
    paidOnly: readBoolean(value, 'paidOnly'),
  };
}

export async function getNotificationFeed(): Promise<NotificationRecord[]> {
  const payload = await readJsonFile<unknown>(NOTIFICATIONS_FILE);
  if (!Array.isArray(payload) || payload.length === 0) {
    return demoNotifications;
  }

  const records = payload
    .map(item => normalizeNotificationRecord(item))
    .filter((item): item is NotificationRecord => item !== null)
    .sort(
      (left, right) =>
        new Date(right.notifiedAt).getTime() - new Date(left.notifiedAt).getTime(),
    );

  return records.length > 0 ? records : demoNotifications;
}

export async function getDashboardFilters(): Promise<DashboardFilters> {
  const payload = await readJsonFile<unknown>(DASHBOARD_FILTERS_FILE);
  if (!payload || typeof payload !== 'object') {
    return defaultDashboardFilters;
  }
  return normalizeDashboardFilters(payload as Partial<DashboardFilters>);
}

export async function saveDashboardFilters(
  filters: DashboardFilters,
): Promise<DashboardFilters> {
  const normalized = normalizeDashboardFilters(filters);
  await mkdir(DATA_DIR, { recursive: true });
  await writeFile(
    DASHBOARD_FILTERS_FILE,
    JSON.stringify(normalized, null, 2),
    'utf8',
  );
  return normalized;
}

export async function getStrategySnapshots(): Promise<StrategySnapshot[]> {
  const payload = await readJsonFile<unknown>(RULES_FILE);
  if (!payload || typeof payload !== 'object') {
    return [];
  }

  const strategies = Array.isArray((payload as JsonObject).strategies)
    ? ((payload as JsonObject).strategies as RawRuleStrategy[])
    : Array.isArray(payload)
      ? (payload as RawRuleStrategy[])
      : [];

  return strategies
    .map(strategy => normalizeStrategy(strategy))
    .filter((item): item is StrategySnapshot => item !== null);
}

async function readJsonFile<T>(filePath: string): Promise<T | null> {
  try {
    const raw = await readFile(filePath, 'utf8');
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function normalizeNotificationRecord(value: unknown): NotificationRecord | null {
  if (!value || typeof value !== 'object') {
    return null;
  }

  const record = value as JsonObject;
  const eventValue = record.event;
  if (!eventValue || typeof eventValue !== 'object') {
    return null;
  }

  const event = eventValue as SignalEvent;
  const context = isObject(record.context) ? (record.context as SignalContext) : {};
  const summary = buildSummary(event, context, record.summary);
  const id = asString(record.id) || asString(event.id);
  const strategyId = asString(record.strategyId) || asString(record.strategy) || 'unknown';

  if (!id) {
    return null;
  }

  return {
    id,
    notifiedAt: asIsoDate(record.notifiedAt) ?? new Date().toISOString(),
    strategyId,
    channels: asStringArray(record.channels),
    message: asString(record.message) || '',
    event,
    context,
    summary,
  };
}

function buildSummary(
  event: SignalEvent,
  context: SignalContext,
  summaryValue: unknown,
): NotificationRecord['summary'] {
  const summary = isObject(summaryValue) ? summaryValue : {};
  const xxyy = isObject(context.xxyy) ? context.xxyy : {};
  const twitter = isObject(context.twitter) ? context.twitter : {};
  const dexscreener = isObject(context.dexscreener) ? context.dexscreener : {};

  return {
    paid: asBoolean(summary.paid) ?? Boolean(dexscreener.paid ?? event.subtype === 'token_profiles_latest'),
    marketCap: asNumber(summary.marketCap) ?? asNumber(xxyy.market_cap),
    holderCount: asNumber(summary.holderCount) ?? asNumber(xxyy.holder_count),
    communityCount: asNumber(summary.communityCount) ?? asNumber(twitter.community_count),
    followersCount: asNumber(summary.followersCount) ?? asNumber(twitter.followers_count),
    twitterUsername:
      asString(summary.twitterUsername) ?? asString(twitter.username) ?? null,
    dexscreenerUrl:
      asString(summary.dexscreenerUrl) ?? asString(dexscreener.url) ?? null,
    telegramUrl:
      asString(summary.telegramUrl) ?? asString(xxyy.project_telegram_url) ?? null,
  };
}

function normalizeStrategy(strategy: RawRuleStrategy): StrategySnapshot | null {
  const id = asString(strategy.id);
  if (!id) {
    return null;
  }

  return {
    id,
    enabled: strategy.enabled !== false,
    source: asString(strategy.source) || 'any',
    chains: asStringArray(strategy.chains),
    channels: asStringArray(strategy.notify).length
      ? asStringArray(strategy.notify)
      : asStringArray(strategy.action?.channels),
    minHolderCount:
      findNumberCondition(
        strategy.entry_rule,
        'xxyy.holder_count',
        '>=',
      ) ?? findNumberConditionList(strategy.entry_conditions, 'xxyy.holder_count', '>='),
    maxHolderCount:
      findNumberCondition(
        strategy.reject_rule,
        'xxyy.holder_count',
        '>',
      ) ?? findNumberConditionList(strategy.reject_conditions, 'xxyy.holder_count', '>'),
    maxMarketCap:
      findNumberCondition(
        strategy.reject_rule,
        'xxyy.market_cap',
        '>',
      ) ?? findNumberConditionList(strategy.reject_conditions, 'xxyy.market_cap', '>'),
    trackedKolNames: findStringListCondition(
      strategy.entry_rule,
      'xxyy.kol_names',
      'contains_any',
    ),
    trackedFollowAddresses: findStringListCondition(
      strategy.entry_rule,
      'xxyy.follow_addresses',
      'contains_any',
    ),
  };
}

function findNumberConditionList(
  conditions: RawRuleCondition[] | undefined,
  field: string,
  op: string,
): number | null {
  if (!Array.isArray(conditions)) {
    return null;
  }
  for (const condition of conditions) {
    if (condition.field === field && condition.op === op) {
      return asNumber(condition.value);
    }
  }
  return null;
}

function findNumberCondition(
  rule: RawRuleCondition | undefined,
  field: string,
  op: string,
): number | null {
  const matches = collectConditions(rule, field, op)
    .map(condition => asNumber(condition.value))
    .filter((value): value is number => value !== null);

  return matches.length > 0 ? matches[0] : null;
}

function findStringListCondition(
  rule: RawRuleCondition | undefined,
  field: string,
  op: string,
): string[] {
  const matches = collectConditions(rule, field, op)
    .flatMap(condition => asStringArray(condition.value))
    .map(item => item.trim())
    .filter(Boolean);

  return Array.from(new Set(matches));
}

function collectConditions(
  rule: RawRuleCondition | undefined,
  field: string,
  op: string,
): RawRuleCondition[] {
  if (!rule || typeof rule !== 'object') {
    return [];
  }

  const matches: RawRuleCondition[] = [];
  if (rule.field === field && rule.op === op) {
    matches.push(rule);
  }

  if (Array.isArray(rule.conditions)) {
    for (const condition of rule.conditions) {
      matches.push(...collectConditions(condition, field, op));
    }
  }

  return matches;
}

function sanitizeNumericInput(value: string | undefined): string {
  if (!value) {
    return '';
  }
  const trimmed = value.trim();
  if (!trimmed) {
    return '';
  }
  return /^-?\d+(\.\d+)?$/.test(trimmed) ? trimmed : '';
}

function readString(
  value: Partial<DashboardFilters> | Record<string, unknown> | null | undefined,
  key: keyof DashboardFilters,
): string {
  if (!value || typeof value !== 'object') {
    return '';
  }
  const raw = value[key];
  return typeof raw === 'string' ? raw.trim() : '';
}

function readBoolean(
  value: Partial<DashboardFilters> | Record<string, unknown> | null | undefined,
  key: keyof DashboardFilters,
): boolean {
  if (!value || typeof value !== 'object') {
    return false;
  }
  return Boolean(value[key]);
}

function asIsoDate(value: unknown): string | null {
  const raw = asString(value);
  if (!raw) {
    return null;
  }
  const date = new Date(raw);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map(item => asString(item))
    .filter((item): item is string => item !== null);
}

function asNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function asBoolean(value: unknown): boolean | null {
  return typeof value === 'boolean' ? value : null;
}

function isObject(value: unknown): value is JsonObject {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

'use client';

import type { JSX } from 'react';
import { useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import {
  Activity,
  ArrowUpRight,
  Check,
  Copy,
  Layers,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import {
  isStrategyPresetEnabled,
} from '@/lib/strategy-presets';
import type { DashboardFilters, NotificationRecord } from '@/lib/types';
import { cn } from '@/lib/utils';
import {
  asOptionalNumber,
  formatPriceUsd,
  formatRelativeTime,
  formatUsd,
  truncateMiddle,
} from '@/lib/format-utils';

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

export type TokenMarketData = {
  priceUsd: number | null;
  marketCap: number | null;
  fdv: number | null;
  liquidityUsd: number | null;
};

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

export function NotificationListItem({
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
        'flex h-full flex-col rounded-[14px] border border-border bg-[linear-gradient(180deg,rgba(12,15,23,0.98),rgba(9,12,18,0.98))] p-2.5 shadow-[0_10px_24px_rgba(0,0,0,0.16)] transition-colors hover:border-white/[0.12] hover:bg-[linear-gradient(180deg,rgba(15,19,29,0.98),rgba(10,13,20,0.98))]',
        strategyEnabled ? getLaohuangToneClass(strategyState) : '',
      )}
    >
      <div className="flex h-full flex-col gap-2">
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
        </div>

        {strategyEnabled ? (
          <div className="flex flex-wrap gap-2">
            <InfoPill
              icon={Layers}
              label={`首推 FDV ${formatUsd(strategyState.firstSeenFdv)}`}
            />
            <InfoPill
              icon={Activity}
              label={`相对首推 ${formatSignedPercent(strategyChangePercent)}`}
            />
          </div>
        ) : null}

        <div className="grid gap-2.5 text-sm">
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

        </div>
      </div>
    </li>
  );
}

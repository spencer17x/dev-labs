export const RELATIVE_TIME_TICK_MS = 1_000;

export function formatUsd(value: number | null): string | null {
  if (value === null) {
    return null;
  }
  return `$${formatCompactNumber(value)}`;
}

export function formatOptionalNumber(value: number | null): string | null {
  if (value === null) {
    return null;
  }
  return formatCompactNumber(value);
}

export function formatLooseNumber(value: number | null): string | null {
  if (value === null) {
    return null;
  }
  return formatPlainMetric(value);
}

export function formatPriceUsd(value: number | null): string | null {
  if (value === null) {
    return null;
  }

  if (value >= 1) {
    return `$${formatPlainNumber(Number(value.toFixed(4)))}`;
  }

  return `$${trimTrailingZeros(value.toFixed(10))}`;
}

export function formatPlainMetric(value: number): string {
  if (Number.isInteger(value)) {
    return formatPlainNumber(value);
  }

  return trimTrailingZeros(value.toFixed(Math.abs(value) >= 1 ? 4 : 8));
}

export function formatRelativeTime(value: string, currentTimeMs: number): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return 'unknown';
  }

  const diffMs = date.getTime() - currentTimeMs;
  const direction = diffMs <= 0 ? 'ago' : 'later';
  const absDiffMs = Math.abs(diffMs);

  if (absDiffMs < 60_000) {
    const diffSeconds = Math.floor(absDiffMs / 1_000);
    return `${diffSeconds}s ${direction}`;
  }

  const diffMinutes = Math.floor(absDiffMs / 60_000);
  if (diffMinutes < 60) {
    return `${diffMinutes}m ${direction}`;
  }

  const diffHours = Math.floor(absDiffMs / 3_600_000);
  if (diffHours < 24) {
    return `${diffHours}h ${direction}`;
  }

  const diffDays = Math.floor(absDiffMs / 86_400_000);
  return `${diffDays}d ${direction}`;
}

export function formatCompactNumber(value: number): string {
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

export function formatCompactUnit(value: number): string {
  const abs = Math.abs(value);
  const decimals = abs < 100 ? 1 : 0;
  return trimTrailingZeros(value.toFixed(decimals));
}

export function formatPlainNumber(value: number): string {
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

export function trimTrailingZeros(value: string): string {
  return value.replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1');
}

export function areStringArraysEqual(
  left: readonly string[],
  right: readonly string[],
): boolean {
  if (left.length !== right.length) {
    return false;
  }

  return left.every((value, index) => value === right[index]);
}

export function parseNumericFilter(value: string): number | null {
  if (!value.trim()) {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function asOptionalNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  return null;
}

export function padNumber(value: number): string {
  return value.toString().padStart(2, '0');
}

export function truncateText(value: string, maxLength: number): string {
  if (value.length <= maxLength) {
    return value;
  }

  return `${value.slice(0, Math.max(0, maxLength - 1))}…`;
}

export function truncateMiddle(
  value: string,
  start = 6,
  end = 4,
): string {
  if (value.length <= start + end + 3) {
    return value;
  }

  return `${value.slice(0, start)}...${value.slice(-end)}`;
}

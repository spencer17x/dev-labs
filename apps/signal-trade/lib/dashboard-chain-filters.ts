export const ALL_DASHBOARD_CHAINS = ['solana', 'base', 'bsc'] as const;

export type DashboardChain = (typeof ALL_DASHBOARD_CHAINS)[number];

const DASHBOARD_CHAIN_SET = new Set<string>(ALL_DASHBOARD_CHAINS);

export function normalizeDashboardChains(value: unknown): DashboardChain[] {
  if (!Array.isArray(value)) {
    return [...ALL_DASHBOARD_CHAINS];
  }

  const normalized = Array.from(
    new Set(
      value.filter(
        (item): item is DashboardChain =>
          typeof item === 'string' && DASHBOARD_CHAIN_SET.has(item),
      ),
    ),
  );

  if (normalized.length === 0) {
    return [...ALL_DASHBOARD_CHAINS];
  }

  return normalized;
}

export function areAllDashboardChainsSelected(
  value: readonly string[],
): boolean {
  return ALL_DASHBOARD_CHAINS.every(chain => value.includes(chain));
}

export function matchesDashboardChainSelection(
  chain: string | null | undefined,
  selectedChains: readonly string[],
): boolean {
  if (areAllDashboardChainsSelected(selectedChains)) {
    return true;
  }

  if (!chain) {
    return false;
  }

  return selectedChains.includes(chain);
}

export function toggleDashboardChainSelection(
  selectedChains: readonly string[],
  chain: DashboardChain,
): DashboardChain[] {
  const nextSelected = selectedChains.includes(chain)
    ? selectedChains.filter(item => item !== chain)
    : [...selectedChains, chain];

  return normalizeDashboardChains(nextSelected);
}

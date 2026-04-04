export function matchesMarketCapRange(
  marketCap: number | null | undefined,
  options: {
    max: number | null;
    min: number | null;
  },
): boolean {
  if (options.min === null && options.max === null) {
    return true;
  }

  if (marketCap == null) {
    return false;
  }

  if (options.min !== null && marketCap < options.min) {
    return false;
  }

  if (options.max !== null && marketCap > options.max) {
    return false;
  }

  return true;
}

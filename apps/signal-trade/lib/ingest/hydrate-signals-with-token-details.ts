type StoredSignalTokenLike = {
  address?: string | null;
  chain?: string | null;
};

export type StoredSignalLike = {
  context: {
    token?: StoredSignalTokenLike;
  };
  event: {
    chain?: string | null;
    token: {
      address?: string | null;
    };
  };
};

type HydrateStoredSignalsOptions<TSignal extends StoredSignalLike, TDetail> = {
  buildTokenKey: (
    chainId: string | null | undefined,
    tokenAddress: string | null | undefined,
  ) => string | null;
  fetchDetailsByChain: (
    chainId: string,
    tokenAddresses: string[],
  ) => Promise<Record<string, TDetail | null>>;
  maxWaitMs: number;
  mergeSignalWithDetail: (signal: TSignal, detail: TDetail) => TSignal;
};

export async function hydrateStoredSignalsWithTokenDetails<
  TSignal extends StoredSignalLike,
  TDetail,
>(
  signals: TSignal[],
  options: HydrateStoredSignalsOptions<TSignal, TDetail>,
): Promise<TSignal[]> {
  const addressesByChain = new Map<string, Set<string>>();

  for (const signal of signals) {
    const chain = normalizeString(signal.event.chain ?? signal.context.token?.chain);
    const address = normalizeString(signal.event.token.address ?? signal.context.token?.address);
    if (!chain || !address) {
      continue;
    }

    if (!addressesByChain.has(chain)) {
      addressesByChain.set(chain, new Set());
    }

    addressesByChain.get(chain)!.add(address);
  }

  if (addressesByChain.size === 0) {
    return signals;
  }

  const detailsByTokenKey = new Map<string, TDetail | null>();
  const didComplete = await waitForHydrationDeadline(
    Promise.all(
      Array.from(addressesByChain.entries()).map(async ([chain, addresses]) => {
        try {
          const details = await options.fetchDetailsByChain(chain, Array.from(addresses));
          for (const [address, detail] of Object.entries(details)) {
            const key = options.buildTokenKey(chain, address);
            if (!key) {
              continue;
            }

            detailsByTokenKey.set(key, detail);
          }
        } catch {
          // Best-effort enrichment only. Keep the original signal context on failure.
        }
      }),
    ),
    options.maxWaitMs,
  );

  if (!didComplete) {
    return signals;
  }

  return signals.map(signal => {
    const key = options.buildTokenKey(
      signal.event.chain ?? signal.context.token?.chain,
      signal.event.token.address ?? signal.context.token?.address,
    );
    if (!key) {
      return signal;
    }

    const detail = detailsByTokenKey.get(key) ?? null;
    if (!detail) {
      return signal;
    }

    return options.mergeSignalWithDetail(signal, detail);
  });
}

function normalizeString(value: string | null | undefined): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

async function waitForHydrationDeadline(
  task: Promise<unknown>,
  maxWaitMs: number,
): Promise<boolean> {
  if (maxWaitMs <= 0) {
    return false;
  }

  let timer: ReturnType<typeof setTimeout> | null = null;

  try {
    const result = await Promise.race([
      task.then(() => true).catch(() => true),
      new Promise<boolean>(resolve => {
        timer = setTimeout(() => resolve(false), maxWaitMs);
      }),
    ]);

    return result;
  } finally {
    if (timer) {
      clearTimeout(timer);
    }
  }
}

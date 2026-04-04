'use client';

import { useEffect, useRef, useState } from 'react';

import type { DexScreenerPairRaw, DexScreenerTokensByChainResponse } from '@/lib/dexscreener-api-types';
import type { NotificationRecord } from '@/lib/types';

import type { TokenMarketData } from '../components/dashboard/notification-list-item';

interface UseMarketDataEnrichmentResult {
  marketDataVersion: number;
  getMarketData: (chain: string, address: string) => TokenMarketData | null;
}

export function useMarketDataEnrichment(
  notifications: NotificationRecord[],
): UseMarketDataEnrichmentResult {
  const marketDataCacheRef = useRef(new Map<string, TokenMarketData>());
  const enrichingRef = useRef(new Set<string>());
  const [marketDataVersion, setMarketDataVersion] = useState(0);

  useEffect(() => {
    const toEnrich = new Map<string, string[]>(); // chain → addresses

    for (const record of notifications) {
      const chain = record.event.chain ?? record.context.token?.chain ?? null;
      const address =
        record.context.token?.address ?? record.event.token.address ?? null;
      if (!chain || !address) continue;

      const key = `${chain}:${address}`;
      if (marketDataCacheRef.current.has(key)) continue;
      if (enrichingRef.current.has(key)) continue;

      // Only enrich when both price and market cap are missing
      if (record.summary.priceUsd !== null || record.summary.marketCap !== null) {
        continue;
      }

      enrichingRef.current.add(key);
      if (!toEnrich.has(chain)) toEnrich.set(chain, []);
      toEnrich.get(chain)!.push(address);
    }

    if (toEnrich.size === 0) return;

    let pendingUpdates = 0;

    for (const [chain, addresses] of toEnrich) {
      // Batch into groups of 30 (API limit)
      for (let i = 0; i < addresses.length; i += 30) {
        const batch = addresses.slice(i, i + 30);
        pendingUpdates++;
        void fetch(
          `https://api.dexscreener.com/tokens/v1/${chain}/${batch.join(',')}`,
        )
          .then(r => r.json())
          .then((pairs: DexScreenerTokensByChainResponse | unknown) => {
            if (!Array.isArray(pairs)) return;
            for (const pair of pairs) {
              if (!pair || typeof pair !== 'object') continue;
              const p = pair as DexScreenerPairRaw;
              const baseToken = p.baseToken;
              const addr =
                typeof baseToken?.address === 'string'
                  ? baseToken.address
                  : null;
              if (!addr) continue;
              const key = `${chain}:${addr}`;
              const liquidity = p.liquidity;
              const data: TokenMarketData = {
                priceUsd:
                  typeof p.priceUsd === 'string'
                    ? Number(p.priceUsd)
                    : typeof p.priceUsd === 'number'
                      ? p.priceUsd
                      : null,
                marketCap:
                  typeof p.marketCap === 'number' ? p.marketCap : null,
                fdv: typeof p.fdv === 'number' ? p.fdv : null,
                liquidityUsd:
                  typeof liquidity?.usd === 'number' ? liquidity.usd : null,
              };
              // Prefer pairs with actual market data (highest liquidity wins)
              const existing = marketDataCacheRef.current.get(key);
              if (
                !existing ||
                (data.liquidityUsd ?? 0) > (existing.liquidityUsd ?? 0)
              ) {
                marketDataCacheRef.current.set(key, data);
              }
            }
          })
          .catch(() => {
            for (const addr of batch) {
              enrichingRef.current.delete(`${chain}:${addr}`);
            }
          })
          .finally(() => {
            pendingUpdates--;
            if (pendingUpdates === 0) {
              setMarketDataVersion(v => v + 1);
            }
          });
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [notifications]);

  function getMarketData(chain: string, address: string): TokenMarketData | null {
    return marketDataCacheRef.current.get(`${chain}:${address}`) ?? null;
  }

  return { marketDataVersion, getMarketData };
}

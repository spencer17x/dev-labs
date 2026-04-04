import type { SignalEvent } from '../types';
import {
  normalizeDexSubscriptions,
  parseDexSubscriptionPayload,
  type DexScreenerSubscription,
} from './dexscreener';

export type RuntimeIngestInput = {
  limit?: number;
  payload: unknown;
  subscription?: string;
};

export type RuntimeIngestParsed = {
  events: SignalEvent[];
  subscription: DexScreenerSubscription;
};

export function parseRuntimeIngestInput(
  input: RuntimeIngestInput,
): RuntimeIngestParsed {
  const subscription = normalizeDexSubscriptions(
    typeof input.subscription === 'string' ? [input.subscription] : undefined,
  )[0];
  const limit =
    typeof input.limit === 'number' && input.limit > 0
      ? Math.trunc(input.limit)
      : undefined;

  return {
    events: parseDexSubscriptionPayload(subscription, input.payload, limit),
    subscription,
  };
}

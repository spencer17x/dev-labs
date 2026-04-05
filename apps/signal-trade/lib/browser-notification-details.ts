import {
  mergeSignalContextWithDexTokenDetail,
  type DexTokenPairDetailsLike,
} from './dex-token-context';
import {
  buildNotificationRecords,
  type StoredSignal,
} from './ingest/build-notification-records';
import type { NotificationRecord } from './types';

const DETAIL_BATCH_SIZE = 30;
const BROWSER_DETAIL_BACKFILL_MAX_WAIT_MS = 10_000;

export type FetchNotificationDetailsByChain = (
  chainId: string,
  tokenAddresses: string[],
) => Promise<Record<string, DexTokenPairDetailsLike | null>>;

type BackfillNotificationsOptions = {
  batchSize?: number;
  fetchDetailsByChain: FetchNotificationDetailsByChain;
  maxWaitMs?: number;
};

type StreamBackfilledNotificationsOptions = BackfillNotificationsOptions & {
  onBatch: (notifications: NotificationRecord[]) => Promise<void> | void;
};

export function splitDisplayReadyNotifications(
  notifications: NotificationRecord[],
): {
  deferredNotifications: NotificationRecord[];
  immediateNotifications: NotificationRecord[];
} {
  const deferredNotifications: NotificationRecord[] = [];
  const immediateNotifications: NotificationRecord[] = [];

  for (const record of notifications) {
    if (shouldBackfillNotificationDetails(record)) {
      deferredNotifications.push(record);
      continue;
    }

    immediateNotifications.push(record);
  }

  return {
    deferredNotifications,
    immediateNotifications,
  };
}

export function shouldBackfillNotificationDetails(record: NotificationRecord): boolean {
  const chain = record.event.chain ?? record.context.token?.chain ?? null;
  const address = record.context.token?.address ?? record.event.token.address ?? null;
  if (!chain || !address) {
    return false;
  }

  return (
    !record.context.token?.name ||
    !record.context.token?.symbol ||
    record.context.dexscreener?.fdv == null ||
    record.context.dexscreener?.marketCap == null ||
    record.context.dexscreener?.priceUsd == null ||
    record.context.dexscreener?.liquidityUsd == null
  );
}

export async function buildBackfilledNotifications(
  notifications: NotificationRecord[],
  options: BackfillNotificationsOptions,
): Promise<NotificationRecord[]> {
  const merged: NotificationRecord[] = [];

  await streamBackfilledNotifications(notifications, {
    ...options,
    onBatch: batch => {
      merged.push(...batch);
    },
  });

  return merged;
}

export async function streamBackfilledNotifications(
  notifications: NotificationRecord[],
  options: StreamBackfilledNotificationsOptions,
): Promise<void> {
  const batchSize =
    typeof options.batchSize === 'number' && options.batchSize > 0
      ? Math.trunc(options.batchSize)
      : DETAIL_BATCH_SIZE;
  const maxWaitMs =
    typeof options.maxWaitMs === 'number' && options.maxWaitMs >= 0
      ? options.maxWaitMs
      : BROWSER_DETAIL_BACKFILL_MAX_WAIT_MS;

  for (const batch of buildNotificationBatches(notifications, batchSize)) {
    const detailsByAddress = await waitForDetails(
      options.fetchDetailsByChain(batch.chain, batch.addresses),
      maxWaitMs,
    );
    if (!detailsByAddress) {
      continue;
    }

    const nextNotifications = mergeNotificationBatchWithDetails(
      batch.notifications,
      detailsByAddress,
    );
    if (nextNotifications.length === 0) {
      continue;
    }

    await options.onBatch(nextNotifications);
  }
}

function buildNotificationBatches(
  notifications: NotificationRecord[],
  batchSize: number,
): Array<{
  addresses: string[];
  chain: string;
  notifications: NotificationRecord[];
}> {
  const notificationsByChain = new Map<
    string,
    Map<string, NotificationRecord[]>
  >();

  for (const record of notifications) {
    const chain = normalizeString(record.event.chain ?? record.context.token?.chain);
    const address = normalizeAddress(
      record.context.token?.address ?? record.event.token.address,
    );
    if (!chain || !address) {
      continue;
    }

    if (!notificationsByChain.has(chain)) {
      notificationsByChain.set(chain, new Map());
    }

    const byAddress = notificationsByChain.get(chain)!;
    if (!byAddress.has(address)) {
      byAddress.set(address, []);
    }

    byAddress.get(address)!.push(record);
  }

  const batches: Array<{
    addresses: string[];
    chain: string;
    notifications: NotificationRecord[];
  }> = [];

  for (const [chain, notificationsByAddress] of notificationsByChain) {
    const addresses = Array.from(notificationsByAddress.keys());

    for (let index = 0; index < addresses.length; index += batchSize) {
      const batchAddresses = addresses.slice(index, index + batchSize);
      const batchNotifications = batchAddresses.flatMap(
        address => notificationsByAddress.get(address) ?? [],
      );

      batches.push({
        addresses: batchAddresses,
        chain,
        notifications: batchNotifications,
      });
    }
  }

  return batches;
}

function mergeNotificationBatchWithDetails(
  notifications: NotificationRecord[],
  detailsByAddress: Record<string, DexTokenPairDetailsLike | null>,
): NotificationRecord[] {
  const originalById = new Map(
    notifications.map(record => [record.id, record] as const),
  );
  const signals: StoredSignal[] = [];

  for (const record of notifications) {
    const address = normalizeAddress(
      record.context.token?.address ?? record.event.token.address,
    );
    if (!address) {
      continue;
    }

    const detail = detailsByAddress[address] ?? null;
    if (!detail) {
      continue;
    }

    signals.push({
      event: record.event,
      context: mergeSignalContextWithDexTokenDetail(
        record.context,
        detail,
      ) as NotificationRecord['context'],
    });
  }

  return buildNotificationRecords(signals).map(record => {
    const original = originalById.get(record.id);
    if (!original) {
      return record;
    }

    return {
      ...record,
      channels: [...original.channels],
      notifiedAt: original.notifiedAt,
    };
  });
}

function normalizeAddress(value: string | null | undefined): string | null {
  const normalized = normalizeString(value);
  return normalized ? normalized.toLowerCase() : null;
}

function normalizeString(value: string | null | undefined): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

async function waitForDetails<T>(
  task: Promise<T>,
  maxWaitMs: number,
): Promise<T | null> {
  if (maxWaitMs <= 0) {
    return null;
  }

  let timer: ReturnType<typeof setTimeout> | null = null;

  try {
    return await Promise.race([
      task.catch(() => null),
      new Promise<null>(resolve => {
        timer = setTimeout(() => resolve(null), maxWaitMs);
      }),
    ]);
  } finally {
    if (timer) {
      clearTimeout(timer);
    }
  }
}

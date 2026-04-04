'use client';

import { useState } from 'react';
import {
  splitDisplayReadyNotifications,
  streamBackfilledNotifications,
  shouldBackfillNotificationDetails,
} from '@/lib/browser-notification-details';
import { refreshDexNotificationsInBrowser } from '@/lib/browser-refresh';
import { fetchDexTokenDetailsByChain } from '@/lib/dexscreener-token-details';
import type { NotificationRecord } from '@/lib/types';
import { WATCH_LIMIT } from '@/lib/watch-utils';

type RefreshState = 'idle' | 'syncing' | 'synced' | 'error';

interface UseSyncNotificationsOptions {
  onNotifications: (records: NotificationRecord[]) => void;
  getSubscriptions: () => string[];
}

interface UseSyncNotificationsResult {
  isRefreshing: boolean;
  refreshState: RefreshState;
  refreshSummary: string;
  syncNotifications: () => Promise<void>;
}

export function useSyncNotifications({
  onNotifications,
  getSubscriptions,
}: UseSyncNotificationsOptions): UseSyncNotificationsResult {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshState, setRefreshState] = useState<RefreshState>('idle');
  const [refreshSummary, setRefreshSummary] = useState('');

  async function syncNotifications(): Promise<void> {
    setIsRefreshing(true);
    setRefreshState('syncing');
    setRefreshSummary('');

    try {
      const selectedWatchSubscriptions = getSubscriptions();
      if (selectedWatchSubscriptions.length === 0) {
        throw new Error('请至少选择一个订阅');
      }

      const payload = await refreshDexNotificationsInBrowser({
        limit: WATCH_LIMIT,
        subscriptions: selectedWatchSubscriptions,
      });
      const nextNotifications = payload.notifications;
      const { deferredNotifications, immediateNotifications } =
        splitDisplayReadyNotifications(nextNotifications);

      if (immediateNotifications.length > 0) {
        onNotifications(immediateNotifications);
      }
      void backfillSyncNotificationDetails(deferredNotifications, onNotifications);
      setRefreshState('synced');
      setRefreshSummary(
        `本次扫描 ${payload.processed ?? 0} 条事件，接收 ${payload.stored ?? 0} 条通知。`,
      );
    } catch (error) {
      setRefreshState('error');
      setRefreshSummary(
        `同步失败：${error instanceof Error ? error.message : '请检查网络连通性和本地运行配置。'}`,
      );
    } finally {
      setIsRefreshing(false);
    }
  }

  return { isRefreshing, refreshState, refreshSummary, syncNotifications };
}

async function backfillSyncNotificationDetails(
  notifications: NotificationRecord[],
  onNotifications: UseSyncNotificationsOptions['onNotifications'],
): Promise<void> {
  const candidates = notifications.filter(shouldBackfillNotificationDetails);
  if (candidates.length === 0) {
    return;
  }

  try {
    await streamBackfilledNotifications(candidates, {
      fetchDetailsByChain: fetchDexTokenDetailsByChain,
      onBatch: nextNotifications => {
        if (nextNotifications.length > 0) {
          onNotifications(nextNotifications);
        }
      },
    });
  } catch {
    // Keep manual refresh responsive even when client-side detail hydration fails.
  }
}

'use client';

import { useState } from 'react';
import type { NotificationRecord, RuntimeRefreshResult } from '@/lib/types';
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

      const response = await fetch('/api/notifications/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          limit: WATCH_LIMIT,
          subscriptions: selectedWatchSubscriptions,
        }),
      });
      const payload = (await response.json().catch(() => ({}))) as Partial<
        RuntimeRefreshResult
      > & {
        message?: string;
      };
      if (!response.ok) {
        throw new Error(
          typeof payload.message === 'string' && payload.message.trim()
            ? payload.message.trim()
            : `unexpected status ${response.status}`,
        );
      }
      const nextNotifications = Array.isArray(payload.notifications)
        ? payload.notifications
        : [];

      onNotifications(nextNotifications);
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

import { SignalTradeDashboard } from '@/components/dashboard/signal-trade-dashboard';
import {
  getDashboardFilters,
  getNotificationFeed,
  getStrategySnapshots,
} from '@/lib/signal-trade-data';

export const dynamic = 'force-dynamic';

export default async function Page() {
  const [initialNotifications, initialFilters, strategies] = await Promise.all([
    getNotificationFeed(),
    getDashboardFilters(),
    getStrategySnapshots(),
  ]);

  return (
    <SignalTradeDashboard
      initialFilters={initialFilters}
      initialNotifications={initialNotifications}
      strategies={strategies}
    />
  );
}

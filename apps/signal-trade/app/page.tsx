import { SignalTradeDashboard } from '@/components/dashboard/signal-trade-dashboard';
import { getDashboardFilters } from '@/lib/signal-trade-data';

export const dynamic = 'force-dynamic';

export default async function Page() {
  const initialNow = Date.now();
  const initialFilters = await getDashboardFilters();

  return (
    <SignalTradeDashboard
      initialFilters={initialFilters}
      initialNow={initialNow}
      initialNotifications={[]}
    />
  );
}

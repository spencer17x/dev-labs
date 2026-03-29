import { NextResponse } from 'next/server';

import {
  getDashboardFilters,
  normalizeDashboardFilters,
  saveDashboardFilters,
} from '@/lib/signal-trade-data';

export async function GET(): Promise<NextResponse> {
  const filters = await getDashboardFilters();
  return NextResponse.json({ filters });
}

export async function PUT(request: Request): Promise<NextResponse> {
  const payload = (await request.json()) as Record<string, unknown>;
  const filters = normalizeDashboardFilters(payload);
  const savedFilters = await saveDashboardFilters(filters);
  return NextResponse.json({ filters: savedFilters });
}

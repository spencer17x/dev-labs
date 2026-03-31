import { NextResponse } from 'next/server';

import { runRuntimeDiagnostics } from '@/lib/runtime/diagnostics';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(): Promise<NextResponse> {
  try {
    const diagnostics = await runRuntimeDiagnostics();
    return NextResponse.json(diagnostics);
  } catch (error) {
    return NextResponse.json(
      {
        error: 'diagnostics_failed',
        message: error instanceof Error ? error.message : 'Unknown diagnostics error',
      },
      { status: 500 },
    );
  }
}

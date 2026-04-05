'use client';

import { useState } from 'react';
import { runBrowserRuntimeDiagnostics } from '@/lib/browser-runtime-diagnostics';
import type { RuntimeDiagnosticsResult } from '@/lib/types';

interface UseDiagnosticsResult {
  isDiagnosing: boolean;
  diagnostics: RuntimeDiagnosticsResult | null;
  diagnosticsError: string;
  runDiagnostics: () => Promise<void>;
}

export function useDiagnostics(): UseDiagnosticsResult {
  const [isDiagnosing, setIsDiagnosing] = useState(false);
  const [diagnostics, setDiagnostics] = useState<RuntimeDiagnosticsResult | null>(null);
  const [diagnosticsError, setDiagnosticsError] = useState('');

  async function runDiagnostics(): Promise<void> {
    setIsDiagnosing(true);
    setDiagnosticsError('');

    try {
      setDiagnostics(await runBrowserRuntimeDiagnostics());
    } catch (error) {
      setDiagnosticsError(
        error instanceof Error ? error.message : 'Unknown diagnostics error',
      );
    } finally {
      setIsDiagnosing(false);
    }
  }

  return { isDiagnosing, diagnostics, diagnosticsError, runDiagnostics };
}

'use client';

import { useState } from 'react';
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
      const response = await fetch('/api/runtime/diagnostics', {
        method: 'POST',
        cache: 'no-store',
      });
      const payload = (await response.json().catch(() => ({}))) as Partial<
        RuntimeDiagnosticsResult
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

      setDiagnostics(payload as RuntimeDiagnosticsResult);
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

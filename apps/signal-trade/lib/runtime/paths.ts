import fs from 'node:fs';
import path from 'node:path';

function resolveSignalTradeDir(): string {
  const candidates = [
    process.cwd(),
    path.join(process.cwd(), 'apps', 'signal-trade'),
  ];

  for (const candidate of candidates) {
    if (fs.existsSync(path.join(candidate, 'next.config.ts'))) {
      return candidate;
    }
  }

  return candidates[0];
}

export const SIGNAL_TRADE_DIR = resolveSignalTradeDir();
export const SIGNAL_TRADE_RUNTIME_CONFIG_FILE = path.join(
  SIGNAL_TRADE_DIR,
  'config.json',
);
export const SIGNAL_TRADE_ENV_FILE = path.join(SIGNAL_TRADE_DIR, '.env');

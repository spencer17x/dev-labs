import fs from 'node:fs';

import { SIGNAL_TRADE_ENV_FILE } from './paths';

let envLoaded = false;

export function loadLocalEnv(): void {
  if (envLoaded) {
    return;
  }
  envLoaded = true;

  if (!fs.existsSync(SIGNAL_TRADE_ENV_FILE)) {
    return;
  }

  const content = fs.readFileSync(SIGNAL_TRADE_ENV_FILE, 'utf8');
  for (const line of content.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) {
      continue;
    }
    const separatorIndex = trimmed.indexOf('=');
    if (separatorIndex <= 0) {
      continue;
    }
    const key = trimmed.slice(0, separatorIndex).trim();
    const rawValue = trimmed.slice(separatorIndex + 1).trim();
    if (!key || process.env[key]) {
      continue;
    }
    process.env[key] = stripQuotes(rawValue);
  }
}

function stripQuotes(value: string): string {
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1);
  }
  return value;
}

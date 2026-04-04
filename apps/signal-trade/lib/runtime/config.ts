import fs from 'node:fs';

import { loadLocalEnv } from './env';
import { SIGNAL_TRADE_RUNTIME_CONFIG_FILE } from './paths';

loadLocalEnv();

type RuntimeConfig = {
  dexscreener: {
    pollIntervalSec: number;
    requestTimeoutSec: number;
    wsHeartbeatSec: number;
    reconnectDelaySec: number;
  };
};

function readRuntimeConfig(): Partial<RuntimeConfig> {
  try {
    if (!fs.existsSync(SIGNAL_TRADE_RUNTIME_CONFIG_FILE)) {
      return {};
    }
    return JSON.parse(
      fs.readFileSync(SIGNAL_TRADE_RUNTIME_CONFIG_FILE, 'utf8'),
    ) as Partial<RuntimeConfig>;
  } catch {
    return {};
  }
}

const runtimeConfig = readRuntimeConfig();

function getNestedNumber(
  section: keyof RuntimeConfig,
  key: string,
  fallback: number,
): number {
  const sectionValue = runtimeConfig[section];
  if (!sectionValue || typeof sectionValue !== 'object') {
    return fallback;
  }
  const value = (sectionValue as Record<string, unknown>)[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function getStringEnv(name: string, fallback = ''): string {
  return (process.env[name] ?? fallback).trim();
}

export const signalTradeConfig = {
  dexscreener: {
    pollIntervalSec: Math.max(getNestedNumber('dexscreener', 'pollIntervalSec', 15), 1),
    requestTimeoutSec: Math.max(
      getNestedNumber('dexscreener', 'requestTimeoutSec', 15),
      1,
    ),
    wsHeartbeatSec: Math.max(
      getNestedNumber('dexscreener', 'wsHeartbeatSec', 30),
      1,
    ),
    reconnectDelaySec: Math.max(
      getNestedNumber('dexscreener', 'reconnectDelaySec', 3),
      1,
    ),
  },

} as const;

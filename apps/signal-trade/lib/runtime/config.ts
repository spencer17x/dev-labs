import fs from 'node:fs';

import { loadLocalEnv } from '@/lib/runtime/env';
import { SIGNAL_TRADE_RUNTIME_CONFIG_FILE } from '@/lib/runtime/paths';

loadLocalEnv();

const DEFAULT_TWITTER_BEARER_TOKEN =
  'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5I8xn5QHj0XuCw%3D1Zv7ttfk8qXzN8kzY5xq9uxZ3sJY8N6t4QeqA';

type RuntimeConfig = {
  dexscreener: {
    pollIntervalSec: number;
    requestTimeoutSec: number;
    wsHeartbeatSec: number;
    reconnectDelaySec: number;
  };
  twitter: {
    requestTimeoutSec: number;
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
  twitter: {
    requestTimeoutSec: Math.max(
      getNestedNumber('twitter', 'requestTimeoutSec', 20),
      1,
    ),
  },
  twitterAuth: {
    bearerToken: getStringEnv(
      'TWITTER_BEARER_TOKEN',
      DEFAULT_TWITTER_BEARER_TOKEN,
    ),
    ct0: getStringEnv('TWITTER_CT0'),
    authToken: getStringEnv('TWITTER_AUTH_TOKEN'),
  },
  xxyyAuth: {
    authorization: getStringEnv('XXYY_AUTHORIZATION'),
    infoToken: getStringEnv('XXYY_INFO_TOKEN'),
    cookie: getStringEnv('XXYY_COOKIE'),
  },
} as const;

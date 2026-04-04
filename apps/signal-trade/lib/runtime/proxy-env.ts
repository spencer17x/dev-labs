const PROXY_ENV_KEYS = [
  'HTTP_PROXY',
  'HTTPS_PROXY',
  'ALL_PROXY',
  'http_proxy',
  'https_proxy',
  'all_proxy',
] as const;

let proxyBypassDepth = 0;
let savedProxyEnv: Record<string, string | undefined> | null = null;

export async function withProxyEnvDisabled<T>(
  callback: () => Promise<T>,
): Promise<T> {
  if (proxyBypassDepth === 0) {
    savedProxyEnv = snapshotProxyEnv();
    clearProxyEnv();
  }

  proxyBypassDepth += 1;

  try {
    return await callback();
  } finally {
    proxyBypassDepth -= 1;

    if (proxyBypassDepth === 0) {
      restoreProxyEnv(savedProxyEnv);
      savedProxyEnv = null;
    }
  }
}

function snapshotProxyEnv(): Record<string, string | undefined> {
  return Object.fromEntries(PROXY_ENV_KEYS.map(key => [key, process.env[key]]));
}

function clearProxyEnv(): void {
  for (const key of PROXY_ENV_KEYS) {
    delete process.env[key];
  }
}

function restoreProxyEnv(
  snapshot: Record<string, string | undefined> | null,
): void {
  if (!snapshot) {
    return;
  }

  for (const key of PROXY_ENV_KEYS) {
    const value = snapshot[key];
    if (typeof value === 'string') {
      process.env[key] = value;
      continue;
    }

    delete process.env[key];
  }
}

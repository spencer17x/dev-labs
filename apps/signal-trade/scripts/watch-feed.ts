import { runWatchLoop, normalizeWatchTransport } from '@/lib/runtime/watch-loop';

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const controller = new AbortController();

  installShutdownHandlers(controller);

  await runWatchLoop({
    signal: controller.signal,
    intervalSec: args.intervalSec,
    limit: args.limit,
    subscriptions: args.subscriptions,
    transport: normalizeWatchTransport(args.transport),
    onLog: message => {
      console.log(message);
    },
  });
}

function parseArgs(argv: string[]): {
  intervalSec?: number;
  limit?: number;
  subscriptions?: string[];
  transport?: string;
} {
  const result: {
    intervalSec?: number;
    limit?: number;
    subscriptions?: string[];
    transport?: string;
  } = {};

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === '--interval-sec') {
      const next = Number(argv[index + 1]);
      if (Number.isFinite(next)) {
        result.intervalSec = next;
        index += 1;
      }
      continue;
    }

    if (token === '--limit') {
      const next = Number(argv[index + 1]);
      if (Number.isFinite(next)) {
        result.limit = next;
        index += 1;
      }
      continue;
    }

    if (token === '--transport') {
      const next = argv[index + 1];
      if (next && !next.startsWith('--')) {
        result.transport = next;
        index += 1;
      }
      continue;
    }

    if (token === '--subscriptions') {
      const values: string[] = [];
      while (argv[index + 1] && !argv[index + 1].startsWith('--')) {
        values.push(argv[index + 1]);
        index += 1;
      }
      result.subscriptions = values;
    }
  }

  return result;
}

function installShutdownHandlers(controller: AbortController): void {
  const shutdown = (signalName: NodeJS.Signals): void => {
    console.log(`[signal-trade] received ${signalName}, closing watcher`);
    controller.abort();
  };

  process.once('SIGINT', shutdown);
  process.once('SIGTERM', shutdown);
}

void main();

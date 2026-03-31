import { refreshNotificationFeed } from '@/lib/runtime/refresh-feed';

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const result = await refreshNotificationFeed({
    limit: args.limit,
    subscriptions: args.subscriptions,
  });

  console.log(
    JSON.stringify(
      {
        generatedAt: result.generatedAt,
        processed: result.processed,
        stored: result.stored,
        subscriptions: result.subscriptions,
        visibleNotifications: result.notifications.length,
      },
      null,
      2,
    ),
  );
}

function parseArgs(argv: string[]): {
  limit?: number;
  subscriptions?: string[];
} {
  const result: { limit?: number; subscriptions?: string[] } = {};

  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === '--limit') {
      const next = Number(argv[index + 1]);
      if (Number.isFinite(next)) {
        result.limit = next;
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

void main();

export type NotificationSocialLink = {
  label: string;
  type: 'other' | 'telegram' | 'twitter' | 'website';
  url: string;
};

type NotificationRecordLike = {
  context: {
    dexscreener?: {
      links?: Array<Record<string, unknown>>;
      socials?: Array<{
        handle?: string | null;
        platform?: string | null;
        url?: string | null;
      }>;
      websites?: string[];
    };
    token?: {
      address?: string | null;
      name?: string | null;
      symbol?: string | null;
    };
  };
  event: {
    token: {
      address?: string | null;
      name?: string | null;
      symbol?: string | null;
    };
  };
};

export function buildNotificationIdentity(
  record: NotificationRecordLike,
): {
  address: string | null;
  name: string | null;
  primaryLabel: string;
  secondaryLabel: string | null;
  symbol: string | null;
} {
  const address =
    firstString(record.context.token?.address, record.event.token.address);
  const symbol =
    firstString(record.context.token?.symbol, record.event.token.symbol);
  const name =
    firstString(record.context.token?.name, record.event.token.name);
  const primaryLabel = symbol ?? name ?? 'UNKNOWN';
  const secondaryLabel =
    symbol &&
    name &&
    symbol.localeCompare(name, undefined, { sensitivity: 'accent' }) !== 0
      ? name
      : null;

  return {
    address,
    name,
    primaryLabel,
    secondaryLabel,
    symbol,
  };
}

export function buildNotificationSocialLinks(
  record: NotificationRecordLike,
): NotificationSocialLink[] {
  const links: NotificationSocialLink[] = [];
  const seen = new Set<string>();

  for (const website of record.context.dexscreener?.websites ?? []) {
    pushLink(links, seen, {
      label: 'Website',
      type: 'website',
      url: website,
    });
  }

  for (const social of record.context.dexscreener?.socials ?? []) {
    const url = firstString(social.url);
    if (!url) {
      continue;
    }

    const type = normalizeLinkType(social.platform, url);
    pushLink(links, seen, {
      label: labelForType(type, social.platform),
      type,
      url,
    });
  }

  for (const link of record.context.dexscreener?.links ?? []) {
    const url =
      typeof link.url === 'string' && link.url.trim() ? link.url.trim() : null;
    if (!url) {
      continue;
    }

    const type = normalizeLinkType(
      typeof link.type === 'string' ? link.type : null,
      url,
    );
    pushLink(links, seen, {
      label: labelForType(type, typeof link.type === 'string' ? link.type : null),
      type,
      url,
    });
  }

  return links.sort((left, right) => {
    return priorityForType(left.type) - priorityForType(right.type);
  });
}

function pushLink(
  links: NotificationSocialLink[],
  seen: Set<string>,
  candidate: NotificationSocialLink,
): void {
  const url = firstString(candidate.url);
  if (!url) {
    return;
  }

  const key = url.toLowerCase();
  if (seen.has(key)) {
    return;
  }

  seen.add(key);
  links.push({
    ...candidate,
    url,
  });
}

function labelForType(
  type: NotificationSocialLink['type'],
  rawType: string | null | undefined,
): string {
  if (type === 'twitter') {
    return 'X';
  }

  if (type === 'telegram') {
    return 'Telegram';
  }

  if (type === 'website') {
    return 'Website';
  }

  return firstString(rawType)?.trim() ?? 'Link';
}

function normalizeLinkType(
  rawType: string | null | undefined,
  url: string,
): NotificationSocialLink['type'] {
  const normalizedType = rawType?.trim().toLowerCase() ?? '';
  const normalizedUrl = url.toLowerCase();

  if (
    normalizedType === 'twitter' ||
    normalizedType === 'x' ||
    normalizedUrl.includes('x.com/') ||
    normalizedUrl.includes('twitter.com/')
  ) {
    return 'twitter';
  }

  if (
    normalizedType === 'telegram' ||
    normalizedType === 'tg' ||
    normalizedUrl.includes('t.me/')
  ) {
    return 'telegram';
  }

  if (
    normalizedType === 'website' ||
    normalizedType === 'site'
  ) {
    return 'website';
  }

  return 'other';
}

function priorityForType(type: NotificationSocialLink['type']): number {
  if (type === 'website') {
    return 0;
  }

  if (type === 'twitter') {
    return 1;
  }

  if (type === 'telegram') {
    return 2;
  }

  return 3;
}

function firstString(...values: Array<string | null | undefined>): string | null {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }

  return null;
}

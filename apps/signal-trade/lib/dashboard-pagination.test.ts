import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildNotificationPagination,
  buildPaginationItems,
  normalizePageSizeInput,
  type PaginationItem,
} from './dashboard-pagination.ts';
import type { NotificationRecord } from './types.ts';

test('buildNotificationPagination sorts newest first before slicing the current page', () => {
  const notifications = [
    buildNotification('older', '2026-04-04T00:00:00.000Z'),
    buildNotification('newest', '2026-04-04T00:02:00.000Z'),
    buildNotification('middle', '2026-04-04T00:01:00.000Z'),
  ];

  const page = buildNotificationPagination(notifications, {
    currentPage: 1,
    pageSize: 2,
  });

  assert.equal(page.totalItems, 3);
  assert.equal(page.totalPages, 2);
  assert.deepEqual(
    page.items.map(record => record.id),
    ['newest', 'middle'],
  );
});

test('normalizePageSizeInput supports preset options and valid custom values', () => {
  assert.equal(normalizePageSizeInput('10'), 10);
  assert.equal(normalizePageSizeInput('20'), 20);
  assert.equal(normalizePageSizeInput('30'), 30);
  assert.equal(normalizePageSizeInput(' 42 '), 42);
  assert.equal(normalizePageSizeInput('0'), 10);
  assert.equal(normalizePageSizeInput('abc'), 10);
});

test('buildPaginationItems keeps first and last pages with ellipsis around the current window', () => {
  const items = buildPaginationItems({
    currentPage: 8,
    totalPages: 15,
  });

  assert.deepEqual(
    items.map(item => serializePaginationItem(item)),
    ['page:1', 'ellipsis:start', 'page:7', 'page:8', 'page:9', 'ellipsis:end', 'page:15'],
  );
});

function buildNotification(id: string, notifiedAt: string): NotificationRecord {
  return {
    id,
    notifiedAt,
    channels: [],
    message: id,
    event: {
      id,
      source: 'dexscreener',
      subtype: 'token_profiles_latest',
      timestamp: new Date(notifiedAt).getTime(),
      chain: 'solana',
      token: {
        address: id,
      },
    },
    context: {},
    summary: {
      paid: false,
      imageUrl: null,
      marketCap: null,
      holderCount: null,
      liquidityUsd: null,
      priceUsd: null,
      communityCount: null,
      dexscreenerUrl: null,
      telegramUrl: null,
    },
  };
}

function serializePaginationItem(item: PaginationItem): string {
  return item.type === 'page' ? `page:${item.page}` : `ellipsis:${item.id}`;
}

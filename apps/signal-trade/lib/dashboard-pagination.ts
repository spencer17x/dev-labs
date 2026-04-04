import type { NotificationRecord } from './types.ts';

export const DEFAULT_NOTIFICATION_PAGE_SIZE = 10;
export const NOTIFICATION_PAGE_SIZE_PRESETS = [10, 20, 30] as const;

export type PaginationItem =
  | {
      type: 'page';
      isCurrent: boolean;
      page: number;
    }
  | {
      type: 'ellipsis';
      id: 'start' | 'end';
    };

export function normalizePageSizeInput(
  value: string,
  fallback = DEFAULT_NOTIFICATION_PAGE_SIZE,
): number {
  const parsed = Number.parseInt(value.trim(), 10);

  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback;
  }

  return parsed;
}

export function buildNotificationPagination(
  notifications: NotificationRecord[],
  options: {
    currentPage: number;
    pageSize: number;
  },
): {
  currentPage: number;
  items: NotificationRecord[];
  pageSize: number;
  totalItems: number;
  totalPages: number;
} {
  const pageSize = Math.max(1, Math.floor(options.pageSize));
  const totalItems = notifications.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const currentPage = clampPage(options.currentPage, totalPages);
  const startIndex = (currentPage - 1) * pageSize;

  return {
    currentPage,
    items: [...notifications]
      .sort(
        (left, right) =>
          new Date(right.notifiedAt).getTime() - new Date(left.notifiedAt).getTime(),
      )
      .slice(startIndex, startIndex + pageSize),
    pageSize,
    totalItems,
    totalPages,
  };
}

export function buildPaginationItems({
  currentPage,
  totalPages,
}: {
  currentPage: number;
  totalPages: number;
}): PaginationItem[] {
  if (totalPages <= 1) {
    return [{ type: 'page', page: 1, isCurrent: true }];
  }

  if (totalPages <= 5) {
    return Array.from({ length: totalPages }, (_, index) => ({
      type: 'page' as const,
      page: index + 1,
      isCurrent: index + 1 === clampPage(currentPage, totalPages),
    }));
  }

  const safeCurrentPage = clampPage(currentPage, totalPages);

  if (safeCurrentPage <= 3) {
    return [
      ...pagesToItems([1, 2, 3, 4], safeCurrentPage),
      { type: 'ellipsis', id: 'end' },
      ...pagesToItems([totalPages], safeCurrentPage),
    ];
  }

  if (safeCurrentPage >= totalPages - 2) {
    return [
      ...pagesToItems([1], safeCurrentPage),
      { type: 'ellipsis', id: 'start' },
      ...pagesToItems(
        [totalPages - 3, totalPages - 2, totalPages - 1, totalPages],
        safeCurrentPage,
      ),
    ];
  }

  return [
    ...pagesToItems([1], safeCurrentPage),
    { type: 'ellipsis', id: 'start' },
    ...pagesToItems(
      [safeCurrentPage - 1, safeCurrentPage, safeCurrentPage + 1],
      safeCurrentPage,
    ),
    { type: 'ellipsis', id: 'end' },
    ...pagesToItems([totalPages], safeCurrentPage),
  ];
}

function pagesToItems(
  pages: number[],
  currentPage: number,
): PaginationItem[] {
  return pages.map(page => ({
    type: 'page' as const,
    page,
    isCurrent: page === currentPage,
  }));
}

function clampPage(page: number, totalPages: number): number {
  if (!Number.isFinite(page)) {
    return 1;
  }

  return Math.min(Math.max(1, Math.floor(page)), totalPages);
}

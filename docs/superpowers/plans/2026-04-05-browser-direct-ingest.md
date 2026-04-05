# Browser Direct Ingest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove browser scan/watch dependency on `POST /api/runtime/ingest` by extracting a shared, browser-safe ingest pipeline.

**Architecture:** Shared parsing and notification-building logic moves out of `lib/runtime/` into browser-safe modules under `lib/`. Browser HTTP/WS flows call the shared ingest pipeline directly, while Node runtime watchers keep their server-side IO and configuration behavior.

**Tech Stack:** Next.js 16, React 19, TypeScript, node:test

---

### Task 1: Lock Browser Expectations With Tests

**Files:**
- Modify: `apps/signal-trade/lib/browser-refresh.test.ts`
- Create or Modify: `apps/signal-trade/lib/ingest/ingest-dex-payload.test.ts`

- [ ] **Step 1: Write the failing tests**

Add a browser refresh test that expects:
- latest Dex HTTP fetches still happen
- `/api/runtime/ingest` is not called
- `notifications/processed/stored/subscriptions` are still returned

Add an ingest unit test that parses a latest payload and returns `NotificationRecord[]` with expected token and summary fields.

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test apps/signal-trade/lib/browser-refresh.test.ts apps/signal-trade/lib/ingest/ingest-dex-payload.test.ts`

Expected: FAIL because browser refresh still posts to `/api/runtime/ingest` and the shared ingest module does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create the shared ingest entrypoint and wire browser refresh to call it directly.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test apps/signal-trade/lib/browser-refresh.test.ts apps/signal-trade/lib/ingest/ingest-dex-payload.test.ts`

Expected: PASS

### Task 2: Extract Browser-Safe Shared Parsing Modules

**Files:**
- Create: `apps/signal-trade/lib/dexscreener-payload.ts`
- Modify: `apps/signal-trade/lib/runtime/dexscreener.ts`
- Modify: `apps/signal-trade/lib/runtime/runtime-ingest.ts`
- Modify: `apps/signal-trade/lib/runtime/dexscreener.test.ts`

- [ ] **Step 1: Write the failing parser adaptation tests**

Extend parser tests to import from the new shared parser module and assert the existing event shape still holds.

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test apps/signal-trade/lib/runtime/dexscreener.test.ts`

Expected: FAIL until parser exports move to the shared module.

- [ ] **Step 3: Write minimal implementation**

Move browser-safe logic out of `lib/runtime/dexscreener.ts`:
- subscription normalization
- latest payload parsing
- latest URL builders
- browser-safe event id helper

Leave Node fetch/watch logic in `lib/runtime/dexscreener.ts`.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test apps/signal-trade/lib/runtime/dexscreener.test.ts`

Expected: PASS

### Task 3: Extract Shared Notification-Building Pipeline

**Files:**
- Create: `apps/signal-trade/lib/ingest/enrich-signal-event.ts`
- Create: `apps/signal-trade/lib/ingest/build-notification-records.ts`
- Create: `apps/signal-trade/lib/ingest/hydrate-signals-with-token-details.ts`
- Create: `apps/signal-trade/lib/ingest/ingest-dex-payload.ts`
- Modify: `apps/signal-trade/lib/runtime/enrichment.ts`
- Modify: `apps/signal-trade/lib/runtime/notification-store.ts`
- Modify: `apps/signal-trade/lib/runtime/signal-token-hydration.ts`
- Modify: `apps/signal-trade/lib/runtime/refresh-feed.ts`

- [ ] **Step 1: Write the failing pipeline tests**

Add or adapt unit tests so the shared ingest pipeline is expected to:
- enrich signals
- hydrate token details through an injected fetcher
- build `NotificationRecord[]`

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test apps/signal-trade/lib/runtime/runtime-ingest.test.ts apps/signal-trade/lib/runtime/signal-token-hydration.test.ts`

Expected: FAIL until the shared modules exist and runtime wrappers point to them.

- [ ] **Step 3: Write minimal implementation**

Move the pure logic into `lib/ingest/*` and convert runtime files into wrappers or re-exports where that keeps churn low.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test apps/signal-trade/lib/runtime/signal-token-hydration.test.ts apps/signal-trade/lib/runtime/runtime-ingest.test.ts`

Expected: PASS

### Task 4: Rewire Browser HTTP And WS Flows

**Files:**
- Modify: `apps/signal-trade/lib/browser-refresh.ts`
- Modify: `apps/signal-trade/hooks/use-browser-watch.ts`
- Modify: `apps/signal-trade/hooks/use-sync-notifications.ts`

- [ ] **Step 1: Write the failing behavior tests**

Add assertions that browser HTTP scan and WS payload ingestion call the shared ingest pipeline directly and no longer rely on `/api/runtime/ingest`.

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test apps/signal-trade/lib/browser-refresh.test.ts`

Expected: FAIL until browser callers stop posting to `/api/runtime/ingest`.

- [ ] **Step 3: Write minimal implementation**

Update browser callers to:
- parse payload text locally
- call shared ingest directly
- preserve current immediate/deferred notification handling

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test apps/signal-trade/lib/browser-refresh.test.ts`

Expected: PASS

### Task 5: Remove Dead Browser Ingest Route

**Files:**
- Delete: `apps/signal-trade/app/api/runtime/ingest/route.ts`
- Delete or simplify: `apps/signal-trade/lib/runtime/runtime-ingest.ts`
- Modify: `apps/signal-trade/README.md`

- [ ] **Step 1: Write the failing documentation/reference check**

Search for remaining live references to `/api/runtime/ingest` and `runtime-ingest`.

- [ ] **Step 2: Run reference check**

Run: `rg -n "/api/runtime/ingest|runtime-ingest" apps/signal-trade`

Expected: references only remain in docs/tests that are about the old behavior and need updating or removal.

- [ ] **Step 3: Write minimal implementation**

Remove dead route/module usage and update README flow descriptions to reflect browser-direct ingest.

- [ ] **Step 4: Run reference check again**

Run: `rg -n "/api/runtime/ingest|runtime-ingest" apps/signal-trade`

Expected: no stale runtime references remain outside intentional historical context.

### Task 6: Verify The Migration

**Files:**
- Modify as needed from previous tasks only

- [ ] **Step 1: Run targeted tests**

Run: `node --test apps/signal-trade/lib/browser-refresh.test.ts apps/signal-trade/lib/runtime/dexscreener.test.ts apps/signal-trade/lib/runtime/signal-token-hydration.test.ts apps/signal-trade/lib/ingest/ingest-dex-payload.test.ts`

Expected: PASS

- [ ] **Step 2: Run type-check**

Run: `pnpm --filter signal-trade type-check`

Expected: PASS

- [ ] **Step 3: Review worktree**

Run: `git status --short`

Expected: only intended migration files are modified, plus any pre-existing unrelated user changes.

# Browser Direct Ingest Design

**Goal:** Remove the page runtime's dependency on `POST /api/runtime/ingest` by moving Dex latest-payload ingestion into browser-reusable shared modules while keeping the CLI/runtime watcher behavior unchanged.

## Scope

This design only changes the web dashboard scan/watch flows in `apps/signal-trade`.

It does not redesign filter behavior, strategy logic, or the CLI/runtime watch loop. It also does not change the DexScreener APIs the app depends on.

## Current Problem

The page already talks to DexScreener directly for latest HTTP and WebSocket feeds, then forwards the raw payload to `/api/runtime/ingest` for normalization. That adds an extra application hop without creating a necessary security boundary. The route also overlaps with browser-side detail backfill, so the page path currently splits responsibility between server-side ingest and client-side hydration.

## Proposed Architecture

Split the current ingest implementation into:

1. Shared, browser-safe payload parsing and notification-building modules.
2. Browser fetch/orchestration code that calls the shared ingest functions directly.
3. Node-only runtime fetch/watch code that keeps using server-side IO helpers.

The shared layer remains responsible for:

- normalizing subscriptions
- parsing latest HTTP/WS payloads into `SignalEvent[]`
- enriching events into `SignalContext`
- hydrating signals with token details through an injected fetcher
- building final `NotificationRecord[]`

The browser layer becomes responsible for:

- fetching latest HTTP payloads
- opening latest WebSocket feeds
- parsing raw payload text locally
- calling the shared ingest function directly
- updating dashboard state and best-effort detail backfill

The Node runtime remains responsible for:

- Dex HTTP fetches with proxy bypass
- Dex WebSocket consumption for CLI watch mode
- config-driven reconnect/timeouts

## File Boundaries

Create or extract shared browser-safe modules under `apps/signal-trade/lib/`:

- `lib/dexscreener-payload.ts`
  - `normalizeDexSubscriptions`
  - `parseDexSubscriptionPayload`
  - latest endpoint URL builders
  - browser-safe event id hashing
- `lib/ingest/enrich-signal-event.ts`
- `lib/ingest/build-notification-records.ts`
- `lib/ingest/hydrate-signals-with-token-details.ts`
- `lib/ingest/ingest-dex-payload.ts`

Keep Node-only modules under `lib/runtime/`:

- `runtime/dexscreener.ts`
- `runtime/refresh-feed.ts`
- `runtime/watch-loop.ts`
- `runtime/proxy-env.ts`
- `runtime/config.ts`

## Data Flow

### Browser HTTP scan

`Dex latest HTTP -> payloadText -> local parse -> local ingest -> token detail hydration -> NotificationRecord[] -> page state`

### Browser WS watch

`Dex latest WebSocket -> message text -> local parse -> local ingest -> token detail hydration -> NotificationRecord[] -> page state`

### CLI/runtime watch

Unchanged:

`Dex HTTP/WS -> runtime parser/ingest -> token detail hydration -> log output`

## API Changes

Page scan/watch flows stop calling `POST /api/runtime/ingest`.

The route and its thin wrapper module can be removed once browser callers are gone and no other code references them.

No external DexScreener API dependency changes:

- latest HTTP endpoints stay the same
- latest WS endpoints stay the same
- `GET /tokens/v1/:chain/:addresses` stays the detail source

## Risks

1. `parseDexSubscriptionPayload()` currently lives in a Node-only file that imports `node:crypto`. A browser-safe event id strategy is required before moving it client-side.
2. Browser and Node must continue to produce the same `NotificationRecord` shape from the same payloads.
3. Any code path that still imports parser helpers from `lib/runtime/dexscreener.ts` after the split will keep browser-incompatible dependencies alive.

## Testing Strategy

- Add tests for browser HTTP scan that prove the flow no longer posts to `/api/runtime/ingest`.
- Add tests for browser WS ingest helper behavior that prove raw payload text is ingested locally.
- Keep parser and notification-building unit tests passing against the extracted shared modules.
- Run targeted `node:test` files plus `pnpm --filter signal-trade type-check`.

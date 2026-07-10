# Trending Alert Bot Hardening Design

## Context

The current bot has eight confirmed correctness and reliability defects across
contract storage, dry-run behavior, Telegram lifecycle handling, multiplier
safety checks, narrative enrichment, and scheduled reports. Runtime contract
data can be rebuilt from upstream data, so this change does not preserve legacy
contract-tracking rows across schema changes. Telegram chat subscriptions and
notification modes remain durable.

## Goals

- Prevent multiplier notifications for contracts currently marked as honeypots.
- Make a dead Telegram worker fatal to the main process so PM2 can restart it.
- Replace destructive ad-hoc contract migrations with deterministic schema
  recreation when the contract schema version changes.
- Make dry-run isolated, side-effect free, and usable without subscribed chats.
- Produce narrative scores from structured evidence instead of URL-only shells.
- Enforce the configured minimum narrative evidence count.
- Analyze each candidate at most once per scan, including failed analyses.
- Retry only failed scheduled-report deliveries and advance the global report
  marker only after all applicable chats succeed.
- Add Robinhood Chain as a first-class single-chain target and include it in
  the existing multi-chain target.
- Preserve existing candidate selection, notification modes, multiplier rules,
  narrative display-only behavior, and report contents.

## Non-Goals

- Preserve legacy contract rows, Telegram message IDs, multiplier history, or
  narrative cache rows after an incompatible schema change.
- Introduce a message queue, asynchronous monitor architecture, or new service.
- Change notification thresholds, candidate ranking, cooldowns, or report
  schedules.
- Use narrative scores to filter notifications.

## Design Decisions

### Contract Schema Lifecycle

Define an explicit contract-schema version in `db_storage.py` and persist it
with SQLite `PRAGMA user_version`. On startup:

1. Create chat and runtime-state tables if missing.
2. Compare the stored contract-schema version and expected table columns.
3. If they do not match, drop the contract relation tables, contracts table,
   and narrative cache table in foreign-key-safe order.
4. Recreate the current schema and store the new version.

This deliberately resets rebuildable tracking data. It never renames a live
parent table, so SQLite cannot rewrite child foreign keys to a temporary table.
Extra or missing columns are treated as a schema mismatch rather than migrated.
`telegram_chats` and its notification modes are not dropped.

### Telegram Worker Health

`TelegramNotifier.start_bot()` clears prior readiness/error state, starts the
worker, and waits for either readiness or a startup error. A startup error or
timeout raises a dedicated runtime exception to the main thread.

The monitor checks worker health before each scan. A dead thread, missing loop,
or recorded fatal error raises outside the retrying scan block, terminates the
main process, and lets PM2 apply its existing restart policy. Normal
`KeyboardInterrupt` shutdown remains graceful.

### Isolated Dry-Run

`main.py --dry-run` replaces `BOT_DATA_DIR` with a temporary directory before
runtime modules are imported. The temporary directory exists for the whole run
and is removed afterward. Therefore contract rows, narrative cache rows, and
runtime markers cannot reach the production database.

The monitor skips silent initialization in dry-run mode. If no chats exist in
the temporary database, it uses one synthetic chat for processing. It performs
one normal candidate scan, formats and prints notifications, never starts
Telegram, never processes scheduled reports, and exits without sleeping after
the scan. Multiplier notifications are naturally absent because the temporary
database has no previously delivered messages.

### Multiplier Safety

Extract the honeypot check used by initial-candidate filtering into a shared
helper. Before multiplier processing, skip contracts currently marked as
honeypots and clear any pending multiplier confirmation for that contract.
Other existing multiplier eligibility rules remain unchanged.

### Narrative Evidence and Scoring

The xAI request uses Responses API structured output with an explicit JSON
schema. The response contains the existing narrative fields plus structured
evidence items: URL, excerpt, author handle/id, timestamp, and engagement
counts.

The provider also extracts URLs from official response citations/annotations.
Only evidence whose URL appears in those citations is accepted. Locally:

- author handles are derived from X status URLs when possible;
- exact token-address and symbol/name matches are calculated from the evidence
  excerpt rather than trusted model booleans;
- numeric engagement fields are normalized to non-negative integers;
- influencer hits receive source credit only when their evidence URL is in the
  accepted evidence set and the claimed account matches the evidence author.

The service materializes evidence once and returns no analysis when its count
is below `NARRATIVE_MIN_EVIDENCE`. Insufficient results are neither cached nor
displayed. Narrative failure still falls back to the base notification.

Within one `scan_once()` call, a local map keyed by chain and token address
stores the display result or `None`. The first eligible chat performs the lazy
analysis; all later chats reuse success or failure. Persistent cache behavior
across scans remains unchanged.

### Scheduled Report Delivery

Use `runtime_state` to store a report marker per chat in addition to the current
global marker. For a due report:

1. Skip chats already marked successful for that report marker.
2. Send to each remaining active chat.
3. Persist the per-chat marker only when Telegram returns that chat's message
   ID.
4. Persist the global marker only when every applicable chat is successful.

If one chat fails, the next scan retries only that chat. A restart during the
report window keeps successful-chat markers and therefore does not duplicate
their reports. Manual `/report` generation does not read or write scheduled
delivery markers.

### Robinhood Chain Support

XXYY uses `robin` consistently for the page route, the `x-chain` request
header, and the `chainId` field returned by the trending API. The existing
`/api/data/list/trending` and `/api/data/holders/kol` endpoints accept that
header without a separate request shape. Pair-page routes carry a pair address;
the trending payload continues to expose both `pairAddress` and
`tokenAddress`, so the bot keeps its current token-based storage identity and
passes both values to the KOL request.

Add a `robin` runtime target backed by `ROBIN_TELEGRAM_BOT_TOKEN` and
`data/robin-bot`, and append `robin` to the `multi` target. Add matching CLI,
environment example, PM2, README, and XXYY-button entries. Robinhood Chain
trending rows commonly have no `launchFrom`, so the base filter treats `robin`
like `eth` for that one presence check. All other candidate ordering, KOL
requirements, honeypot handling, cooldowns, notification modes, and multiplier
rules stay unchanged.

## Error Handling

- Schema recreation is transactional; a failed recreation rolls back.
- Telegram worker failure is fatal instead of being absorbed by the scan retry
  loop.
- Narrative provider, parsing, citation, and evidence failures return no
  narrative and do not block the base alert.
- Scheduled-report failures remain due until all target chats succeed.
- Dry-run errors exit after the single attempted scan and never touch
  production state.

## Testing

Add regression tests before implementation for all eight defects:

- honeypot multiplier suppression and pending-state cleanup;
- Telegram startup failure and post-start worker death;
- contract schema mismatch recreation while preserving chat subscriptions;
- dry-run temporary storage, synthetic chat processing, one-scan exit, and no
  production mutation;
- structured evidence parsing, citation validation, and meaningful scoring;
- minimum-evidence rejection without cache writes;
- one provider call for one failed candidate across multiple chats;
- per-chat scheduled-report retry and global-marker advancement.
- Robin target configuration, multi-target membership, CLI/PM2 exposure, and
  acceptance of otherwise-valid Robin rows with an empty `launchFrom`.

Run focused tests during each change, then run:

```bash
uv run python -m unittest discover -s tests -q
uv run python -m compileall -q .
```

The implementation is complete only when the full suite passes and the app
working tree contains only intentional source, test, and documentation changes.

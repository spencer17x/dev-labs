# Trending Alert Bot Command Latency Design

## Goal

Keep existing command results, alert selection, report contents, and schedules while preventing slow report generation, SQLite access, Telegram delivery failures, and unrelated group traffic from delaying commands.

## Confirmed Causes

- `python-telegram-bot` currently processes one update at a time.
- `/report` runs synchronous multi-chain HTTP work inside the Telegram event loop.
- each multi-chain report loads chains sequentially with a 30-second timeout per chain.
- synchronous Telegram send timeouts leave their coroutine running.
- a catch-all message handler performs a SQLite lookup for every visible group message.
- failed scheduled destinations remain due on every monitor scan; permanent Telegram destination errors therefore create continuous retry load.
- `ChatStorage` reloads the complete chat table for point reads and counters.

## Design

### Telegram command isolation

Configure a bounded update concurrency of 16. Run blocking storage and report-generator calls with `asyncio.to_thread()`. Keep commands semantically identical: `/report` still returns the same formatted report and errors, while other updates can be handled during report generation.

Remove the catch-all message handler because it has no subscription side effect. Subscription remains explicit through `/start`, while bot membership changes continue through `MY_CHAT_MEMBER` updates.

### Report generation

Collect the distinct chains needed by a report, then load their latest contract maps concurrently with a bounded standard-library thread pool. A single report never starts more workers than the number of requested chains. Chain failures retain the existing empty-map fallback, so report content rules do not change.

### Delivery failure control

On synchronous send timeout, cancel the scheduled coroutine. Classify Telegram destination failures in the notifier:

- group migration updates the stored subscription from the old chat ID to the new supergroup ID and retries once;
- permanent destination errors deactivate the subscription;
- transient network and rate-limit errors remain retryable.

Scheduled reports persist a retry timestamp and attempt count per chat/report marker. Failed transient targets use bounded exponential backoff instead of retrying every scan. Successful targets retain their existing per-chat marker and never receive duplicates.

### Storage hot path

Replace full-table reloads for point reads, mode reads/writes, removal, and message counters with targeted SQL statements. Keep the in-memory `data` snapshot only for compatibility with existing callers that inspect it; refresh it only for full-list operations. Enable SQLite WAL and a bounded busy timeout on every connection.

### Observability

Log command queue/handler duration and report generation duration without logging chat IDs or message contents. These timings distinguish Telegram transport delay from local handler delay.

## Error Handling

- Per-chain report failures keep the current fallback behavior.
- Threaded storage/report exceptions are caught by the existing command-level error responses.
- A cancelled send future cannot execute later and add hidden queue load.
- Permanent Telegram destinations are disabled only for explicit permanent errors.
- Transient failures remain eligible after backoff.

## Verification

- A slow `/report` does not block a concurrent lightweight command.
- The application update processor is configured for bounded concurrency.
- five chain fetches overlap rather than consuming five serial timeout windows.
- timed-out synchronous sends cancel their future.
- catch-all group messages are not registered.
- failed scheduled delivery is skipped until its retry time; successful chats are not resent.
- migration and permanent-destination handling update subscription state correctly.
- ChatStorage point operations use targeted SQL and preserve behavior.
- the full unittest suite and Python compilation pass.


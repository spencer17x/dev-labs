# Trending Alert Bot Command Latency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent slow reports, failed destinations, SQLite access, and unrelated group traffic from delaying Telegram commands without changing alert or report business rules.

**Architecture:** Use bounded Telegram update concurrency and move synchronous work to threads. Load independent report chains concurrently, cancel timed-out sends, back off transient scheduled-report failures, disable explicit permanent destinations, migrate group subscriptions, and replace ChatStorage full-table point operations with targeted SQL.

**Tech Stack:** Python 3.11, `unittest`, `asyncio`, `concurrent.futures`, SQLite, `python-telegram-bot` 20.x.

---

### Task 1: Isolate Telegram Commands

**Files:**
- Modify: `apps/trending-alert-bot/telegram_bot.py`
- Test: `apps/trending-alert-bot/tests/test_review_regressions.py`

- [ ] Add tests proving bounded update concurrency is configured, `/report` invokes its synchronous generator outside the event-loop thread, and no catch-all message handler is registered.
- [ ] Run the focused tests and confirm they fail for the current implementation.
- [ ] Add `.concurrent_updates(16)`, use `asyncio.to_thread()` for synchronous command/storage work, remove `filters.ALL`, and add duration logging.
- [ ] Run the focused tests and confirm they pass.

### Task 2: Bound Send Lifetime

**Files:**
- Modify: `apps/trending-alert-bot/telegram_bot.py`
- Test: `apps/trending-alert-bot/tests/test_review_regressions.py`

- [ ] Add a failing test proving `send_sync()` and `send_photo_sync()` cancel their future after timeout.
- [ ] Introduce one shared synchronous coroutine runner that cancels on timeout and preserves the current empty-result behavior.
- [ ] Run focused send tests and confirm they pass.

### Task 3: Load Report Chains Concurrently

**Files:**
- Modify: `apps/trending-alert-bot/monitor_flow.py`
- Test: `apps/trending-alert-bot/tests/test_review_regressions.py`

- [ ] Add a failing barrier-based test proving distinct report-chain loads overlap.
- [ ] Add a focused helper that loads distinct chains with a bounded `ThreadPoolExecutor` and use it from scheduled and manual reports.
- [ ] Preserve the existing empty-map fallback and formatted report behavior.
- [ ] Run the report tests and confirm they pass.

### Task 4: Control Failed Destination Retries

**Files:**
- Modify: `apps/trending-alert-bot/telegram_bot.py`
- Modify: `apps/trending-alert-bot/monitor_flow.py`
- Modify: `apps/trending-alert-bot/chat_storage.py`
- Test: `apps/trending-alert-bot/tests/test_review_regressions.py`
- Test: `apps/trending-alert-bot/tests/test_sqlite_storage.py`

- [ ] Add failing tests for group migration, permanent-target deactivation, transient scheduled-report backoff, and retry-state clearing after success.
- [ ] Implement subscription migration and permanent error classification at the notifier boundary.
- [ ] Store per-chat/report retry attempts and retry timestamps in `runtime_state`; skip attempts before the timestamp and use capped exponential backoff.
- [ ] Run focused delivery tests and confirm they pass.

### Task 5: Optimize ChatStorage Point Operations

**Files:**
- Modify: `apps/trending-alert-bot/chat_storage.py`
- Modify: `apps/trending-alert-bot/db_storage.py`
- Test: `apps/trending-alert-bot/tests/test_sqlite_storage.py`

- [ ] Add tests that preserve get, mode, removal, count, and migration behavior without relying on a full-table reload.
- [ ] Replace point operations with targeted `SELECT`, `UPDATE`, and `UPSERT` statements and enable WAL/busy timeout.
- [ ] Run all storage tests and confirm they pass.

### Task 6: Full Verification

**Files:**
- Verify all intentional changes above.

- [ ] Run `uv run python -m unittest discover -s tests -q` from `apps/trending-alert-bot`.
- [ ] Run `uv run python -m compileall -q .`.
- [ ] Run Black check on changed Python files and inspect `git diff --check` plus the final diff.
- [ ] Confirm every design requirement has a passing regression test and no unrelated files changed.


# Trending Alert Bot Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the eight confirmed storage, dry-run, Telegram, multiplier, narrative, and scheduled-report defects without changing alert-selection business rules.

**Architecture:** Keep the synchronous monitor and SQLite architecture. Rebuild incompatible tracking schemas instead of migrating data, isolate dry-run in a temporary database, make Telegram worker health fatal, validate structured narrative evidence once per candidate per scan, and persist scheduled-report success per chat.

**Tech Stack:** Python 3.11, `unittest`, SQLite, `python-telegram-bot` 20.x, `curl_cffi`, xAI Responses API with `x_search`.

## Global Constraints

- Runtime contract, multiplier, message-id, and narrative-cache data may be discarded and rebuilt after an incompatible schema change.
- Preserve `telegram_chats`, chat activation, notification modes, candidate selection, cooldowns, multiplier thresholds, report schedules, and notification text semantics.
- Dry-run must not read or write the production SQLite database and must finish one scan even when no chats are subscribed.
- Narrative enrichment remains display-only and failure must not block the base alert.
- Do not introduce a queue, background worker service, new dependency, or unrelated refactor.
- Use standard-library `unittest`; the locked environment does not include `pytest`.

---

## File Structure

- `apps/trending-alert-bot/db_storage.py`: owns schema version detection and foreign-key-safe tracking-table recreation.
- `apps/trending-alert-bot/telegram_bot.py`: owns Telegram worker startup and runtime health.
- `apps/trending-alert-bot/main.py`: owns temporary dry-run data-directory lifetime.
- `apps/trending-alert-bot/monitor.py`: owns dry-run loop behavior, Telegram health checks, and report-marker advancement.
- `apps/trending-alert-bot/monitor_flow.py`: owns honeypot multiplier safety, per-scan narrative memoization, and per-chat report delivery state.
- `apps/trending-alert-bot/narrative_provider.py`: owns xAI schema, citations, evidence normalization, and provider validation.
- `apps/trending-alert-bot/narrative_service.py`: owns minimum-evidence enforcement.
- `apps/trending-alert-bot/tests/test_sqlite_storage.py`: schema-reset regression coverage.
- `apps/trending-alert-bot/tests/test_entrypoint_config.py`: dry-run entrypoint isolation coverage.
- `apps/trending-alert-bot/tests/test_review_regressions.py`: monitor, Telegram, memoization, and report regressions.
- `apps/trending-alert-bot/tests/test_narrative_service.py`: structured provider and minimum-evidence coverage.

### Task 1: Replace Contract Migration With Versioned Recreation

**Files:**
- Modify: `apps/trending-alert-bot/db_storage.py`
- Test: `apps/trending-alert-bot/tests/test_sqlite_storage.py`

**Interfaces:**
- Produces: `CONTRACT_SCHEMA_VERSION: int` and `ensure_schema()` behavior that preserves `telegram_chats` while recreating incompatible tracking tables.
- Consumes: existing `connect()`, table creation helpers, and SQLite `PRAGMA user_version`.

- [ ] **Step 1: Write the failing schema-recreation test**

Add a test that creates a chat row plus the legacy JSON-column `contracts` table, calls `ensure_schema()`, and asserts the chat survives while the legacy contract is gone and all relation-table foreign keys point to `contracts`:

```python
def test_incompatible_contract_schema_is_recreated_but_chats_survive(self):
    with tempfile.TemporaryDirectory() as tmp:
        _, chat_storage, _ = load_storage_modules(tmp)
        chat_storage.ChatStorage().add_chat(111, {"type": "group", "title": "Keep Me"})
        import db_storage

        with db_storage.connect() as conn:
            conn.execute("DROP TABLE contract_message_ids")
            conn.execute("DROP TABLE contract_notified_multipliers")
            conn.execute("DROP TABLE contract_pending_multipliers")
            conn.execute("DROP TABLE narrative_analysis")
            conn.execute("DROP TABLE contracts")
            conn.execute(
                """
                CREATE TABLE contracts (
                    chain TEXT NOT NULL,
                    chat_id INTEGER NOT NULL,
                    token_address TEXT NOT NULL,
                    initial_price REAL NOT NULL DEFAULT 0,
                    initial_market_cap REAL NOT NULL DEFAULT 0,
                    push_time TEXT NOT NULL DEFAULT '',
                    notified_multipliers_json TEXT NOT NULL DEFAULT '[]',
                    name TEXT NOT NULL DEFAULT '',
                    symbol TEXT NOT NULL DEFAULT '',
                    telegram_message_ids_json TEXT NOT NULL DEFAULT '{}',
                    pending_multiplier_json TEXT NOT NULL DEFAULT '',
                    last_notify_time TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (chain, chat_id, token_address)
                )
                """
            )
            conn.execute(
                "INSERT INTO contracts (chain, chat_id, token_address) VALUES ('sol', 111, 'OLD')"
            )
            conn.execute("PRAGMA user_version = 1")

        db_storage.ensure_schema()

        with db_storage.connect() as conn:
            self.assertIsNotNone(
                conn.execute("SELECT 1 FROM telegram_chats WHERE chat_id = 111").fetchone()
            )
            self.assertIsNone(
                conn.execute("SELECT 1 FROM contracts WHERE token_address = 'OLD'").fetchone()
            )
            self.assertEqual(
                conn.execute("PRAGMA user_version").fetchone()[0],
                db_storage.CONTRACT_SCHEMA_VERSION,
            )
            for table in (
                "contract_message_ids",
                "contract_notified_multipliers",
                "contract_pending_multipliers",
            ):
                parents = {
                    row["table"]
                    for row in conn.execute(f"PRAGMA foreign_key_list({table})")
                }
                self.assertEqual(parents, {"contracts"})
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
cd apps/trending-alert-bot
uv run python -m unittest tests.test_sqlite_storage.SqliteStorageTests.test_incompatible_contract_schema_is_recreated_but_chats_survive -v
```

Expected: FAIL because the current rename/copy migration preserves `OLD`, loses relation state, or leaves rewritten foreign keys.

- [ ] **Step 3: Implement versioned schema recreation**

Replace `_ensure_contract_schema()` with exact schema checks and foreign-key-safe recreation. Execute individual DDL statements inside an explicit transaction; do not use `ALTER TABLE ... RENAME`:

```python
CONTRACT_SCHEMA_VERSION = 2

_RELATION_TABLES = (
    "contract_message_ids",
    "contract_notified_multipliers",
    "contract_pending_multipliers",
)


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone() is not None


def _contract_schema_is_current(conn: sqlite3.Connection) -> bool:
    if conn.execute("PRAGMA user_version").fetchone()[0] != CONTRACT_SCHEMA_VERSION:
        return False
    if not _table_exists(conn, "contracts"):
        return False
    return _table_columns(conn, "contracts") == _CONTRACT_COLUMNS


def _drop_tracking_tables(conn: sqlite3.Connection):
    for table_name in _RELATION_TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {table_name}")
    conn.execute("DROP TABLE IF EXISTS narrative_analysis")
    conn.execute("DROP TABLE IF EXISTS contracts")


def _recreate_tracking_schema(conn: sqlite3.Connection):
    _drop_tracking_tables(conn)
    _create_contracts_table(conn)
    _create_contract_relation_tables(conn)
    _create_narrative_analysis_table(conn)
    conn.execute(f"PRAGMA user_version = {CONTRACT_SCHEMA_VERSION}")
```

Change `_create_contract_relation_tables()` to issue one `conn.execute()` per `CREATE TABLE`, so it does not force an `executescript()` commit. In `ensure_schema()`, create `telegram_chats` and `runtime_state`, then use `BEGIN IMMEDIATE`/`commit`/`rollback` around recreation. When the schema is current, call the idempotent creation helpers without resetting data.

- [ ] **Step 4: Run focused and storage tests GREEN**

Run:

```bash
uv run python -m unittest tests.test_sqlite_storage -v
```

Expected: all storage tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/trending-alert-bot/db_storage.py apps/trending-alert-bot/tests/test_sqlite_storage.py
git commit -m "fix(trending-alert-bot): rebuild incompatible tracking schema"
```

### Task 2: Make Telegram Worker Failure Fatal

**Files:**
- Modify: `apps/trending-alert-bot/telegram_bot.py`
- Modify: `apps/trending-alert-bot/monitor.py`
- Test: `apps/trending-alert-bot/tests/test_review_regressions.py`

**Interfaces:**
- Produces: `TelegramRuntimeError` and `TelegramNotifier.ensure_healthy() -> None`.
- Consumes: existing `_ready_event`, bot thread, bot loop, and PM2 process restart behavior.

- [ ] **Step 1: Write failing worker-health tests**

Add tests that make `_setup_application()` fail and that construct a ready notifier with a dead thread:

```python
def test_telegram_startup_failure_reaches_main_thread(self):
    notifier = telegram_bot.TelegramNotifier()
    with mock.patch.object(
        notifier, "_setup_application", side_effect=RuntimeError("invalid token")
    ), mock.patch("traceback.print_exc"):
        with self.assertRaises(telegram_bot.TelegramRuntimeError):
            notifier.start_bot()


def test_telegram_health_rejects_dead_ready_worker(self):
    notifier = telegram_bot.TelegramNotifier()
    notifier._ready_event.set()
    notifier.bot_loop = mock.Mock()
    notifier.bot_thread = mock.Mock()
    notifier.bot_thread.is_alive.return_value = False

    with self.assertRaises(telegram_bot.TelegramRuntimeError):
        notifier.ensure_healthy()
```

- [ ] **Step 2: Run focused tests RED**

Run:

```bash
uv run python -m unittest \
  tests.test_review_regressions.ReviewRegressionTests.test_telegram_startup_failure_reaches_main_thread \
  tests.test_review_regressions.ReviewRegressionTests.test_telegram_health_rejects_dead_ready_worker -v
```

Expected: FAIL because startup errors stay in the daemon thread and `ensure_healthy` does not exist.

- [ ] **Step 3: Implement startup propagation and health checks**

Add the error type and state:

```python
class TelegramRuntimeError(RuntimeError):
    pass


class TelegramNotifier:
    def __init__(self):
        self._worker_error = None

    def ensure_healthy(self):
        if not self.enabled:
            return
        if self._worker_error is not None:
            raise TelegramRuntimeError("Telegram worker failed") from self._worker_error
        if (
            not self._ready_event.is_set()
            or not self.bot_thread
            or not self.bot_thread.is_alive()
            or self.bot_loop is None
        ):
            raise TelegramRuntimeError("Telegram worker is not running")
```

At the start of `start_bot()`, clear `_ready_event` and `_worker_error`. In `run_bot()`'s exception handler, store the exception and set `_ready_event` so the waiter wakes. After the wait, raise `TelegramRuntimeError` on timeout, stored error, or unhealthy worker.

Before each `while True` scan in `monitor_trending()`, outside the broad retrying `try`, call:

```python
if ENABLE_TELEGRAM and not DRY_RUN:
    notifier.ensure_healthy()
```

- [ ] **Step 4: Run focused tests GREEN**

Run the two tests from Step 2 and expect `OK`.

- [ ] **Step 5: Commit**

```bash
git add apps/trending-alert-bot/telegram_bot.py apps/trending-alert-bot/monitor.py apps/trending-alert-bot/tests/test_review_regressions.py
git commit -m "fix(trending-alert-bot): fail fast on Telegram worker death"
```

### Task 3: Isolate Dry-Run and Block Honeypot Multipliers

**Files:**
- Modify: `apps/trending-alert-bot/main.py`
- Modify: `apps/trending-alert-bot/monitor.py`
- Modify: `apps/trending-alert-bot/monitor_flow.py`
- Test: `apps/trending-alert-bot/tests/test_entrypoint_config.py`
- Test: `apps/trending-alert-bot/tests/test_review_regressions.py`

**Interfaces:**
- Produces: `main.run(cli_args) -> None`, isolated `BOT_DATA_DIR`, one-scan dry-run behavior, and `_is_honeypot_contract(contract) -> bool`.
- Consumes: `BotRuntimeConfig`, `apply_runtime_env`, `ContractStorage.clear_pending_multiplier`.

- [ ] **Step 1: Write failing dry-run and honeypot tests**

Add an entrypoint test with a fake `monitor` module that captures environment values during `run()`:

```python
def test_dry_run_uses_removed_temporary_data_dir(self):
    captured = {}
    fake_monitor = types.SimpleNamespace(
        normalize_clear_targets=lambda value: [],
        monitor_trending=lambda targets: captured.update(
            data_dir=os.environ["BOT_DATA_DIR"],
            dry_run=os.environ["BOT_DRY_RUN"],
        ),
    )
    args = types.SimpleNamespace(target="bsc", clear_storage="", dry_run=True)
    with mock.patch.dict(
        os.environ, {"BSC_TELEGRAM_BOT_TOKEN": "123:test"}, clear=True
    ), mock.patch.dict(sys.modules, {"monitor": fake_monitor}):
        main.run(args)

    self.assertEqual(captured["dry_run"], "1")
    self.assertFalse(os.path.exists(captured["data_dir"]))
```

Add monitor regressions asserting dry-run substitutes chat id `0`, does not call `initialize_storage`, scans once, does not sleep, and returns. Add a multiplier test that seeds a delivered contract plus pending state, supplies `honeyPot.value=True`, and asserts Telegram is not called and pending state is cleared.

- [ ] **Step 2: Run focused tests RED**

Run:

```bash
uv run python -m unittest \
  tests.test_entrypoint_config.EntrypointConfigTests.test_dry_run_uses_removed_temporary_data_dir \
  tests.test_review_regressions.ReviewRegressionTests.test_dry_run_without_chats_scans_once_without_silent_init \
  tests.test_review_regressions.ReviewRegressionTests.test_honeypot_contract_clears_pending_and_skips_multiplier -v
```

Expected: FAIL because `main.run`, synthetic dry-run processing, and multiplier honeypot filtering do not exist.

- [ ] **Step 3: Implement temporary dry-run lifetime**

Refactor the main block into:

```python
def _run_monitor(clear_storage: str):
    from monitor import monitor_trending, normalize_clear_targets

    monitor_trending(normalize_clear_targets(clear_storage))


def run(cli_args):
    runtime_cfg = load_runtime_config(cli_args.target)
    validate_runtime_config(runtime_cfg)
    apply_runtime_env(runtime_cfg)

    if cli_args.dry_run:
        import os
        import tempfile

        with tempfile.TemporaryDirectory(prefix="trending-alert-dry-run-") as data_dir:
            os.environ["BOT_DRY_RUN"] = "1"
            os.environ["BOT_DATA_DIR"] = data_dir
            _run_monitor(cli_args.clear_storage)
        return

    _run_monitor(cli_args.clear_storage)


if __name__ == "__main__":
    run(parse_args())
```

In `monitor.py`, use `[{"chat_id": 0}]` when `DRY_RUN` has no active chats, guard silent initialization and its sleep with `not DRY_RUN`, skip scheduled reports in dry-run, and break immediately after `scan_chains_once()`.

- [ ] **Step 4: Implement shared honeypot safety**

Add to `monitor_flow.py`:

```python
def _is_honeypot_contract(contract: dict) -> bool:
    security = _safe_dict(contract.get("security"))
    return bool(_safe_dict(security.get("honeyPot")).get("value", False))
```

Use it from `_passes_base_filters()`. In the multiplier loop:

```python
if _is_honeypot_contract(contract):
    storage.clear_pending_multiplier(token_address)
    continue
```

- [ ] **Step 5: Run focused tests GREEN**

Run the tests from Step 2 and expect `OK`.

- [ ] **Step 6: Commit**

```bash
git add apps/trending-alert-bot/main.py apps/trending-alert-bot/monitor.py apps/trending-alert-bot/monitor_flow.py apps/trending-alert-bot/tests/test_entrypoint_config.py apps/trending-alert-bot/tests/test_review_regressions.py
git commit -m "fix(trending-alert-bot): isolate dry runs and unsafe multipliers"
```

### Task 4: Use Structured, Cited Narrative Evidence

**Files:**
- Modify: `apps/trending-alert-bot/narrative_provider.py`
- Modify: `apps/trending-alert-bot/narrative_service.py`
- Modify: `apps/trending-alert-bot/narrative_types.py`
- Test: `apps/trending-alert-bot/tests/test_narrative_service.py`

**Interfaces:**
- Produces: structured xAI payload; accepted `List[EvidenceItem]`; minimum-evidence rejection.
- Consumes: xAI response `citations` and output-content `annotations`; existing `compute_narrative_score()`.

- [ ] **Step 1: Write failing structured-evidence tests**

Add provider tests with a response containing one structured evidence row and a matching `url_citation`. Assert the evidence author is derived from the X URL, address match is computed from text, negative counts clamp to zero, and the score exceeds 20. Add a second test where the evidence URL is absent from citations and assert it is rejected.

Add a service test with `NARRATIVE_MIN_EVIDENCE=3` and a provider returning two items:

```python
with mock.patch.object(narrative_service, "_get_provider", return_value=provider), \
     mock.patch.object(narrative_service, "save_analysis") as save:
    result = narrative_service.analyze_contract_narrative(contract, "sol", [])

self.assertIsNone(result)
save.assert_not_called()
```

- [ ] **Step 2: Run focused tests RED**

Run the new provider and service tests and expect failures because the payload is free-form, evidence is URL-only, and minimum evidence is ignored.

- [ ] **Step 3: Add the structured response schema and normalization**

Add `_NARRATIVE_RESPONSE_SCHEMA` with required narrative fields and an `evidence` array. Each evidence object requires `url`, `text`, `author_handle`, `author_id`, `created_at`, `like_count`, `repost_count`, `reply_count`, and `quote_count`, and sets `additionalProperties` to `False`.

Add this to the request payload:

```python
"include": ["no_inline_citations"],
"text": {
    "format": {
        "type": "json_schema",
        "name": "token_narrative",
        "schema": _NARRATIVE_RESPONSE_SCHEMA,
        "strict": True,
    }
},
```

Implement helpers with these exact responsibilities:

```python
def _safe_nonnegative_int(value) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _normalize_url(value: str) -> str:
    parsed = urlsplit(str(value).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), "", ""))


def _x_author_from_url(value: str) -> str:
    parsed = urlsplit(value)
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.netloc.lower() in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}:
        if len(parts) >= 3 and parts[1] == "status" and parts[0].lower() != "i":
            return parts[0].lstrip("@").lower()
    return ""
```

Extract citation URLs from top-level `citations` and every content annotation whose type is `url_citation`. Parse the structured object, accept only evidence URLs present in that set, compute match flags from `NarrativeInput` and evidence text, and derive `llm_result.evidence_links` from accepted evidence.

Filter direct influencer hits so `evidence_url` is accepted and its account equals the evidence author. Keep `mentioned_by_others` only when its URL is accepted; it continues to receive zero source points.

- [ ] **Step 4: Enforce minimum evidence in the service**

Import `NARRATIVE_MIN_EVIDENCE` and insert before scoring/caching:

```python
evidence_items = list(evidence or [])
if len(evidence_items) < NARRATIVE_MIN_EVIDENCE:
    print(
        f"⚠️ [{chain.upper()}] narrative evidence below minimum: "
        f"{contract.get('symbol', 'N/A')} | {token_address} | "
        f"{len(evidence_items)}/{NARRATIVE_MIN_EVIDENCE}"
    )
    return None
```

- [ ] **Step 5: Run narrative tests GREEN**

Run:

```bash
uv run python -m unittest tests.test_narrative_scoring tests.test_narrative_service tests.test_narrative_storage -v
```

Expected: all narrative tests pass.

- [ ] **Step 6: Commit**

```bash
git add apps/trending-alert-bot/narrative_provider.py apps/trending-alert-bot/narrative_service.py apps/trending-alert-bot/narrative_types.py apps/trending-alert-bot/tests/test_narrative_service.py
git commit -m "fix(trending-alert-bot): validate structured narrative evidence"
```

### Task 5: Memoize Narrative Results Per Scan

**Files:**
- Modify: `apps/trending-alert-bot/monitor_flow.py`
- Test: `apps/trending-alert-bot/tests/test_review_regressions.py`

**Interfaces:**
- Produces: optional `narrative_results` map threaded through candidate delivery.
- Consumes: existing `analyze_contract_narrative()` and display dictionaries.

- [ ] **Step 1: Write the failing multi-chat failure test**

Create three active chats, one candidate, and patch `analyze_contract_narrative()` to return `None`. Run `scan_once()` and assert the analysis mock is called once rather than three times.

- [ ] **Step 2: Run the focused test RED**

Run the new test and verify `call_count == 3` before implementation.

- [ ] **Step 3: Implement lazy per-scan memoization**

Create one `narrative_results = {}` in `scan_once()` and pass it to `_process_chat_contracts()` and `_send_candidate_notification()`. In the send function:

```python
cache_key = (chain, token_address)
if narrative_results is not None and cache_key in narrative_results:
    narrative = narrative_results[cache_key]
else:
    narrative = None
    try:
        analysis = analyze_contract_narrative(contract, chain, kol_with_positions)
        if analysis:
            narrative = analysis.to_display_dict()
    except Exception as exc:
        print(
            f"⚠️ [{chain.upper() or 'N/A'}] {contract.get('symbol', 'N/A')} "
            f"叙事分析失败，继续发送基础通知: {token_address} | {exc}"
        )
    if narrative_results is not None:
        narrative_results[cache_key] = narrative
```

Keep the new parameters optional so direct unit calls retain their current interface behavior. Store `None` so failures are memoized.

- [ ] **Step 4: Run focused regression tests GREEN**

Run all candidate-notification tests in `test_review_regressions.py` and expect `OK`.

- [ ] **Step 5: Commit**

```bash
git add apps/trending-alert-bot/monitor_flow.py apps/trending-alert-bot/tests/test_review_regressions.py
git commit -m "fix(trending-alert-bot): memoize narrative analysis per scan"
```

### Task 6: Persist Scheduled Report Success Per Chat

**Files:**
- Modify: `apps/trending-alert-bot/monitor_flow.py`
- Modify: `apps/trending-alert-bot/monitor.py`
- Test: `apps/trending-alert-bot/tests/test_review_regressions.py`

**Interfaces:**
- Produces: `send_summary_report(storages: dict, report_hour: Optional[int] = None) -> bool`.
- Consumes: `get_runtime_state`, `set_runtime_state`, `summary_report_marker`, and notifier message-id dictionaries.

- [ ] **Step 1: Write failing partial-delivery tests**

Create two active chats with storages. On the first call, return `{chat1: 10}` for chat 1 and `{}` for chat 2; assert the function returns `False` and only chat 1 gets a per-chat marker. On the second call, return `{chat2: 20}` and assert chat 1 is skipped, chat 2 is called, and the function returns `True`.

Add a monitor-level test asserting `save_last_summary_marker()` is not called when `send_summary_report()` returns `False`, and is called when it returns `True`.

- [ ] **Step 2: Run focused tests RED**

Run the new tests and expect failure because delivery results are ignored and no per-chat state exists.

- [ ] **Step 3: Implement per-chat scheduled markers**

Add:

```python
_SUMMARY_REPORT_CHAT_STATE_PREFIX = "last_summary_report_marker:"


def _summary_report_chat_state_key(chat_id: int) -> str:
    return f"{_SUMMARY_REPORT_CHAT_STATE_PREFIX}{chat_id}"
```

Change `send_summary_report()` to calculate `report_marker` when `report_hour` is provided, skip chats already carrying that marker, and inspect the notifier result:

```python
message_ids = notifier.send_sync(msg, chat_id=chat_id)
if chat_id not in message_ids:
    all_succeeded = False
    continue
if report_marker:
    set_runtime_state(_summary_report_chat_state_key(chat_id), report_marker)
```

Return `all_succeeded`. Preserve print-only behavior when Telegram is disabled and keep manual `/report` generation unchanged.

In `monitor_trending()`:

```python
if report_time_hour != -1 and not DRY_RUN:
    if send_summary_report(storages, report_time_hour):
        save_last_summary_marker(report_time_hour)
        last_summary_marker = summary_report_marker(report_time_hour)
```

- [ ] **Step 4: Run focused report tests GREEN**

Run the report-related tests in `test_review_regressions.py` and expect `OK`.

- [ ] **Step 5: Run full verification**

Run:

```bash
cd apps/trending-alert-bot
uv run python -m unittest discover -s tests -q
uv run python -m compileall -q .
git diff --check
```

Expected: 0 failures, compile exit 0, and no whitespace errors.

- [ ] **Step 6: Commit**

```bash
git add apps/trending-alert-bot/monitor.py apps/trending-alert-bot/monitor_flow.py apps/trending-alert-bot/tests/test_review_regressions.py docs/superpowers/plans/2026-07-10-trending-alert-bot-hardening.md
git commit -m "fix(trending-alert-bot): retry failed reports per chat"
```

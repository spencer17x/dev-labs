# Telegram Forwarder Optimizations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make `apps/telegram-forwarder` easier to configure, safer to operate under PM2, and more correct around source matching, filtering, forwarding, and validation.

**Architecture:** Keep the existing lightweight Python/Telethon structure. Add normalization and strict validation at config load time, keep filtering pure and unit-testable, keep Telegram side effects contained in services, and expose operational switches through environment variables plus CLI flags.

**Tech Stack:** Python 3.11, Telethon, python-dotenv, uv, unittest.

---

### Task 1: Config Normalization and Validation

**Files:**
- Modify: `apps/telegram-forwarder/config/loader.py`
- Modify: `apps/telegram-forwarder/config/validator.py`
- Test: `apps/telegram-forwarder/tests/test_config_loader.py`

- [x] Add tests for simplified `forwards` syntax, single string targets, disabled group partial configs, environment session precedence, strict malformed-config failures, valid/invalid rule modes, empty keyword/media lists, invalid regex, invalid composite logic, string numeric user IDs, and config path tracking.
- [x] Implement config normalization so both existing `groups` and new `forwards` load into `GroupConfig` / `GroupRule`.
- [x] Make enabled malformed groups fail fast instead of being logged and skipped.
- [x] Make disabled groups allowed to omit `source` and `rules`.
- [x] Make environment `TELEGRAM_SESSION_PATH` override JSON `session_name`.
- [x] Add recursive validation for rule shape and legal enum values.

### Task 2: Source Lookup and Event Handling

**Files:**
- Modify: `apps/telegram-forwarder/config/loader.py`
- Modify: `apps/telegram-forwarder/core/event_handler.py`
- Test: `apps/telegram-forwarder/tests/test_event_handler.py`

- [x] Add tests proving a source configured as `@username` can be found when Telethon emits only numeric `chat.id` plus `chat.username`.
- [x] Update `get_group_config` and `EventHandler` to try numeric ID, bare username, and `@username`.
- [x] Keep numeric private group IDs working with Telethon `-100...` variants.

### Task 3: Filter Semantics

**Files:**
- Modify: `apps/telegram-forwarder/filters/message_filter.py`
- Test: `apps/telegram-forwarder/tests/test_message_filter.py`

- [x] Add tests for empty keyword/media rules, `user_conditional.forward_all`, missing conditions, precompiled regex reuse, string numeric user IDs, invalid values rejected by config validation, and composite logic.
- [x] Fix `forward_all` so `user_conditional.forward_all=true` ignores conditions and `false` requires conditions to match.
- [x] Make empty keyword/media rule lists never match.
- [x] Use precompiled regex objects prepared by config validation when present.
- [x] Support numeric user IDs supplied as strings.

### Task 4: Forwarding Behavior and Delivery Options

**Files:**
- Modify: `apps/telegram-forwarder/config/loader.py`
- Modify: `apps/telegram-forwarder/core/forwarder.py`
- Modify: `apps/telegram-forwarder/services/message_service.py`
- Test: `apps/telegram-forwarder/tests/test_message_service.py`
- Test: `apps/telegram-forwarder/tests/test_forwarder.py`

- [x] Add tests for media-with-caption fallback, copy-only mode, silent mode, duplicate target suppression across matching rules, unsupported fallback messages not counted as success, and bounded FloodWait retry.
- [x] Add rule delivery options: `forward_mode` (`forward` or `copy`), `silent`, and `dedupe`.
- [x] Prefer media fallback over text fallback when both exist.
- [x] Preserve original forward failures in debug logs before fallback.
- [x] Add bounded FloodWait retry controlled by config.

### Task 5: Operations and CLI

**Files:**
- Modify: `apps/telegram-forwarder/main.py`
- Modify: `apps/telegram-forwarder/core/bot.py`
- Modify: `apps/telegram-forwarder/cli/list_my_groups.py`
- Modify: `apps/telegram-forwarder/.env.example`
- Test: `apps/telegram-forwarder/tests/test_cli_helpers.py`
- Test: `apps/telegram-forwarder/tests/test_bot_options.py`

- [x] Add `--config`, `--check-config`, and `--log-level` CLI flags.
- [x] Add `SEND_STARTUP_NOTIFICATION`, `STARTUP_NOTIFICATION_DETAILS`, `LOG_MESSAGE_CONTENT`, and `FLOOD_WAIT_MAX_SECONDS` env settings.
- [x] Default message content logging and startup notifications to off.
- [x] Print final config path and session path during startup.
- [x] Add pure helper tests for usable Telegram config IDs in `list_my_groups.py`.

### Task 6: Documentation and Examples

**Files:**
- Modify: `apps/telegram-forwarder/README.md`
- Modify: `apps/telegram-forwarder/RULES.md`
- Modify: `apps/telegram-forwarder/forward_rules.example.json`
- Modify: `apps/telegram-forwarder/.env.example`

- [x] Add minimal config and simplified `forwards` examples before advanced examples.
- [x] Document all new environment variables and PM2 absolute-path deployment recommendations.
- [x] Remove JSON comments from copy-pasteable JSON examples or label them as explanatory snippets.
- [x] Document security guidance for session files, rules, and logs.
- [x] Document `--check-config` and the stricter validation behavior.

### Task 7: Verification

**Files:**
- Modify: none unless verification finds gaps.

- [x] Run targeted unit tests after each task.
- [x] Run full `.venv/bin/python -m unittest discover -s tests` from `apps/telegram-forwarder`.
- [x] Run `.venv/bin/python main.py --check-config --config forward_rules.example.json`.
- [x] Run import/compile checks with `.venv/bin/python -m py_compile`.
- [x] Inspect `git diff` against every optimization item before claiming completion.

# Trending Alert Bot Hardening Progress

## Objective

Fix the eight reviewed reliability/correctness defects and add XXYY Robinhood
Chain support without changing established alert-selection semantics.

## Baseline

- Branch: `codex/trending-alert-bot-hardening`
- Worktree: `/Users/17a/projects/dev-labs/.worktrees/trending-alert-bot-hardening`
- Baseline tests: 79 passed
- Robin API check: trending and KOL endpoints both accept `x-chain: robin`

## Tasks

- [x] Task 1 — versioned contract-schema recreation
- [x] Task 2 — fatal Telegram worker health propagation
- [x] Task 3 — isolated dry-run and honeypot multiplier safety
- [x] Task 4 — structured, cited narrative evidence
- [x] Task 5 — per-scan narrative memoization
- [x] Task 6 — per-chat scheduled-report delivery markers
- [x] Task 7 — Robinhood Chain runtime support
- [x] Final full verification and review

## Decisions

- Rebuild contract/relation/narrative tables on incompatible schema; preserve
  `telegram_chats` and runtime state.
- Treat `robin` like `eth` only for the missing-`launchFrom` presence check.
- Include `robin` in the `multi` target and keep existing KOL eligibility.

## Evidence

- Task 1 RED: focused recreation test failed because legacy contract `OLD`
  remained after `ensure_schema()`.
- Task 1 review RED: deterministic two-connection interleaving lost the
  competing migrator's `CONCURRENT` contract after the second recreation.
- Task 1 GREEN: `uv run python -m unittest tests.test_sqlite_storage -v`
  passed all 5 storage tests after re-checking under `BEGIN IMMEDIATE`.
- Task 2 RED: both focused worker regressions errored because
  `TelegramRuntimeError` did not exist; the daemon-thread failure had no
  main-thread failure channel and there was no `ensure_healthy()` API.
- Task 2 GREEN: the three focused startup/death/fatal-monitor regressions
  passed, then `uv run python -m unittest tests.test_review_regressions
  tests.test_entrypoint_config -q` passed all 30 relevant tests.
- Task 3 RED: the entrypoint had no callable `run()`, a no-chat dry-run hit
  the silent-init sleep before scanning, and a honeypot reached KOL loading
  instead of clearing its pending multiplier.
- Task 3 GREEN: all three focused regressions passed; the entrypoint/review
  suite passed 33 tests and full discovery passed 87 tests.
- Task 3 review RED: a preloaded production runtime kept `DRY_RUN=False`,
  reopened the production SQLite path, and entered the normal sleep loop;
  normal runs also inherited a prior `BOT_DRY_RUN=1` value.
- Task 3 review GREEN: the entrypoint now evicts only the local config-bound
  runtime graph before import and explicitly sets dry-run state. The cached
  runtime regression and normal reset regression passed, the relevant suite
  passed 34 tests, and full discovery passed 88 tests.
- Task 4 RED: the xAI payload had no structured-output schema; uncited URLs
  and forged direct-influencer claims were accepted; two evidence rows passed
  despite `NARRATIVE_MIN_EVIDENCE=3` and were cached.
- Task 4 GREEN: cited structured rows are normalized and validated locally,
  direct influencer claims require a matching cited author, and insufficient
  evidence returns before scoring or caching. The narrative suite passed 43
  tests and full discovery passed 91 tests.
- Task 4 review RED: an existing cache row bypassed the current minimum policy
  because cache hits returned before validating `raw_result.evidence_count`.
- Task 4 review GREEN: only cache rows with an integer evidence count meeting
  the current minimum are returned; insufficient, missing, and string-valued
  counts refresh through the provider. The narrative suite passed 44 tests and
  full discovery passed 92 tests.
- Task 4 review 2 RED: legacy caches could already contain a sufficient integer
  evidence count even though their evidence had never passed citation
  validation, so the count-only cache check still accepted them.
- Task 4 review 2 GREEN: new analyses store a versioned evidence policy and cache
  reuse requires that exact supported version plus a sufficient integer count.
  The narrative suite passed 44 tests and full discovery passed 92 tests.
- Task 5 RED: one candidate sent to three chats called the narrative service
  three times when it returned `None`.
- Task 5 GREEN: one scan-local `(chain, token_address)` map now reuses success
  and failure results; the focused regression and all 31 review regressions
  passed.
- Task 6 RED: scheduled delivery did not accept a report hour and the monitor
  advanced the global marker after a `False` partial-delivery result.
- Task 6 GREEN: successful chats persist per-chat markers and are skipped on
  retry, failed chats retry alone, and the global marker advances only after
  all applicable chats succeed. The focused tests, 33 review regressions, and
  full 95-test suite passed.
- Task 7 RED: the Robin target was unsupported, `multi` omitted it, both CLIs
  rejected it, PM2/env entries were absent, and safe Robin rows with a null
  launch source were filtered out.
- Task 7 GREEN: `robin` is a single-chain target and part of `multi`; CLI,
  PM2, env, button, API docs, and README exposure are present; only Robin's
  launch-source presence check is relaxed. Four focused and 49 relevant tests
  passed.
- Final review RED: dry-run loop setup errors still retried, and narrative
  status-ID matching did not bind the verified author to the citation URL.
- Final review GREEN: dry-run errors now exit immediately; citation URLs are
  authoritative, X/Twitter/default-port aliases deduplicate by status ID,
  unverified authors receive no direct source credit, Solana address matching
  is case-sensitive, and evidence cache policy v3 invalidates prior results.
- Final verification: live Robin dry-run completed one scan against XXYY;
  103 unit tests passed; Black check, `compileall`, and `git diff --check`
  passed; final holistic review returned ready to merge.

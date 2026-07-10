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

- [ ] Task 1 — versioned contract-schema recreation
- [ ] Task 2 — fatal Telegram worker health propagation
- [ ] Task 3 — isolated dry-run and honeypot multiplier safety
- [ ] Task 4 — structured, cited narrative evidence
- [ ] Task 5 — per-scan narrative memoization
- [ ] Task 6 — per-chat scheduled-report delivery markers
- [ ] Task 7 — Robinhood Chain runtime support
- [ ] Final full verification and review

## Decisions

- Rebuild contract/relation/narrative tables on incompatible schema; preserve
  `telegram_chats` and runtime state.
- Treat `robin` like `eth` only for the missing-`launchFrom` presence check.
- Include `robin` in the `multi` target and keep existing KOL eligibility.

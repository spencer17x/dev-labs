# Commit Message Rules

Commits follow Conventional Commits and only contain a title line (no body or footer). Format:

```
<type>(<scope>): <description>
```

## Type (required)

`feat`, `fix`, `chore`, `refactor`, `docs`, `perf`, `test`.

Append `!` after scope for breaking changes (e.g. `feat(twitter-bot)!: ...`).

## Scope

Required when changes are inside a single app. Use the app directory name:
`trending-alert-bot`, `twitter-bot`, `token-launcher`, `telegram-forwarder`, `telegram-watcher`.

Omit scope only for root/cross-app changes (scripts, CI, workspace config).

## Description

- Imperative mood, lowercase start, no period, ≤72 chars
- Describe *what changed*, not *how*

## Generating Commit Messages

When asked to generate a commit message, always check the staged (`git diff --cached`) or unstaged (`git diff`) changes first. Base the message on the **actual file diffs**, not on conversation context.

If the working tree contains multiple unrelated changes (e.g. a feature change + a docs refactor), suggest splitting into separate commits with distinct messages.

## Examples

- `feat(trending-alert-bot): add per-chat notification mode control`
- `fix(telegram-forwarder): handle empty forward rules gracefully`
- `chore: update pnpm-lock and bump dependencies`
- `refactor(twitter-bot): extract filter logic into utils`
- `feat(token-launcher)!: change deploy config schema`

## PR Gate

All commit messages on PRs to `main` are validated by `conventional-commits.yml`. Invalid messages block merge.

## Branch Naming

Branch names should begin with `experiment/` or `fix/` plus a concise subject.

## PR Checklist

Every PR needs:
- Short description
- Linked issue or task
- Reproduced test commands (pnpm, python, curl payloads)
- List of config or data updates (`.env`, `forward_rules.json`, `db.json`)
- Screenshot bot dialogs or terminal output whenever behavior changes

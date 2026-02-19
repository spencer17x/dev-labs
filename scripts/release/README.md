# Release By Directory

This repository uses directory-scoped releases for `apps/*`.

## Tag format

- `<app>/vX.Y.Z`
- Example: `trending-alert-bot/v0.0.2`

## How version bump is decided

From latest app tag to `HEAD`, only commits touching `apps/<app>` are considered:

- `BREAKING CHANGE` or `type!:` -> major
- `feat:` -> minor
- others -> patch

If an app has no previous tag, first release defaults to `v0.1.0`.

## Workflow

- Workflow file: `.github/workflows/release-by-directory.yml`
- Trigger:
  - push to `main` with changes under `apps/**`
  - `workflow_dispatch` (manual)
- Inputs:
  - `dry_run=true/false`
  - `apps` (required, comma-separated app names)

## PR preview

- Workflow file: `.github/workflows/release-preview.yml`
- Trigger: pull request to `main` with changes under `apps/**` or release scripts
- Behavior: dry-run output for changed app directories only
- PR comment: bot will update one `Release Preview (dry-run)` comment with bump-grouped summary (major/minor/patch/initial) + collapsible full output (same-repo PRs)

## Commit message gate

- Workflow file: `.github/workflows/conventional-commits.yml`
- Trigger: pull request to `main`
- Rule: commit subject must match Conventional Commits (`feat: ...`, `fix(scope): ...`, etc.)

Local validation:

```bash
bash scripts/release/check-conventional-commits.sh <base_sha> <head_sha>
```

## GitHub branch protection (recommended)

Set `main` branch required checks to:

- `Conventional Commits Check / validate`
- `Release Preview / preview`

## Local dry-run

```bash
DRY_RUN=true bash scripts/release/by-directory.sh
```

or:

```bash
pnpm release:dry-run
```

Only run for selected apps:

```bash
DRY_RUN=true CHANGED_APPS=trending-alert-bot,token-launcher bash scripts/release/by-directory.sh
```

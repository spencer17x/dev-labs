# Release By Directory

This repository uses directory-scoped releases for `apps/*`.

## Tag format

- `<app>/vX.Y.Z`
- Example: `trending-alert-bot/v0.0.2`

## How version bump is decided

From latest app tag to `HEAD`, only commits touching `apps/<app>` are considered:

- `type!:` -> major
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
  - `allow_existing_tag_release=true/false` (optional, default `false`)
  - `apps` (required, comma-separated app names)

If `allow_existing_tag_release=true` and an app has no new commits after latest tag, the script can still create a missing GitHub Release for that latest existing tag.

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

The validator enforces the same title-only format, type list, length, punctuation, and app-only scope rules as `.githooks/commit-msg`.

## Local Git hooks

Install the tracked hooks after cloning (the root `prepare` script also does this after `pnpm install`):

```bash
pnpm hooks:install
```

- `pre-commit`: staged whitespace, ignored-file, syntax, and Prettier checks
- `commit-msg`: Conventional Commit subject and scope validation
- `pre-push`: outgoing commit validation plus change-aware builds and tests

The pre-push and remote quality workflow both call `scripts/ci/validate-changes.sh`.

## GitHub branch protection (recommended)

Set `main` branch required checks to:

- `Conventional Commits Check / validate`
- `Quality CI / validate`

`Release Preview / preview` is informational and path-filtered, so it should not be a globally required check.
Also require pull requests and block force pushes to keep invalid direct commits from reaching `main` before CI can report them.

## Local dry-run

```bash
DRY_RUN=true bash scripts/release/by-directory.sh
```

or:

```bash
pnpm release:dry-run
```

Backfill missing release for latest existing tag (no new commits):

```bash
ALLOW_EXISTING_TAG_RELEASE=true CHANGED_APPS=trending-alert-bot bash scripts/release/by-directory.sh
```

Only run for selected apps:

```bash
DRY_RUN=true CHANGED_APPS=trending-alert-bot,token-launcher bash scripts/release/by-directory.sh
```

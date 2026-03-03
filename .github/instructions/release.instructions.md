# Tagging & Release Rules

Releases are directory-scoped and fully automated — **do not manually create tags or releases**.

## Tag Format

`<app>/vX.Y.Z` (e.g. `trending-alert-bot/v1.0.0`)

## Version Bump Rules

Based on commits touching `apps/<app>` since the last tag:

| Commit pattern | Bump |
|---|---|
| `feat(scope)!:` or body contains `BREAKING CHANGE:` | **major** |
| `feat(scope):` | **minor** |
| `fix`, `chore`, `refactor`, etc. | **patch** |
| No previous tag (first release) | **v0.1.0** |

## Automated Workflows

- **Push to `main`** (`release-by-directory.yml`): detects changed apps under `apps/`, creates git tags and GitHub Releases automatically.
- **PR to `main`** (`release-preview.yml`): posts a dry-run release preview as a PR comment showing expected bump type and release notes.
- **Manual dispatch**: run `release-by-directory.yml` with `apps` input (comma-separated) and optional `dry_run` / `allow_existing_tag_release` flags.

## Local Dry-Run

```bash
DRY_RUN=true CHANGED_APPS=trending-alert-bot bash scripts/release/by-directory.sh
```

Only run for selected apps:

```bash
DRY_RUN=true CHANGED_APPS=trending-alert-bot,token-launcher bash scripts/release/by-directory.sh
```

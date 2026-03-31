# Repository Guidelines

## Project Structure & Module Organization
`apps/` contains every app. Bundled TypeScript apps typically use the `src/` → `dist/` path plus `rolldown.config.ts`, and they store env/database samples beside the code for zero-dependency bundles. `apps/signal-trade` is the Next.js exception: UI in `app/` and `components/`, shared code in `lib/`, runtime collectors and rule evaluation in `lib/runtime/`, and local scripts in `scripts/`. Python apps use repo-root `/.python-version` with `uv`, and each app keeps its own `.venv` plus local config samples beside the code. Root configs (`package.json`, `pnpm-workspace.yaml`, `tsconfig.json`) define shared tooling, while `scripts/create-project.ts` (`pnpm new`) scaffolds new work.

## Build, Test & Development Commands
Install shared dependencies with `pnpm install`. For bundled TypeScript apps, run `pnpm --filter <app> dev` for vite-node hot reload, `pnpm --filter <app> build` for rolldown bundles, and `pnpm --filter <app> start:prod` to execute the emitted `dist/index.cjs`. For `signal-trade`, use `pnpm --filter signal-trade dev`, `build`, `start`, `type-check`, plus `runtime:refresh` or `runtime:watch` to populate the local notification feed. Python apps should run `uv python install`, `uv venv`, `uv pip install -r requirements.txt`, then start with `uv run python <entrypoint>.py` from the app directory.

## Detailed Rules

See `.github/instructions/` for topic-specific rules:
- `commit.instructions.md` — commit message format, branch naming, PR checklist
- `release.instructions.md` — tagging, version bumps, automated release workflows
- `coding.instructions.md` — code style, testing, security & configuration

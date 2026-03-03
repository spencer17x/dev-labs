# Repository Guidelines

## Project Structure & Module Organization
`apps/` contains every bot. TypeScript agents (twitter-bot, token-launcher, trending-alert-bot) share the `src/` → `dist/` path plus `rolldown.config.ts`, and they store env/database samples beside the code for zero-dependency bundles. Python services (telegram-forwarder, telegram-watcher) keep orchestration in `core/`, adapters in `services/`, and routing data in `forward_rules.example.json`; create per-app venvs. Root configs (`package.json`, `pnpm-workspace.yaml`, `tsconfig.json`) define shared tooling, while `scripts/create-project.ts` (`pnpm new`) scaffolds new work.

## Build, Test & Development Commands
Install shared dependencies with `pnpm install`. For TypeScript work, run `pnpm --filter <app> dev` for vite-node hot reload, `pnpm --filter <app> build` for rolldown bundles, and `pnpm --filter <app> start:prod` to execute the emitted `dist/index.cjs`. Python bots should create a local env (`python -m venv venv && source venv/bin/activate`), install `pip install -r requirements.txt`, and start with `python main.py`.

## Detailed Rules

See `.github/instructions/` for topic-specific rules:
- `commit.instructions.md` — commit message format, branch naming, PR checklist
- `release.instructions.md` — tagging, version bumps, automated release workflows
- `coding.instructions.md` — code style, testing, security & configuration

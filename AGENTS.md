# Repository Guidelines

## Project Structure & Module Organization
`apps/` contains every bot. TypeScript agents (twitter-bot, token-launcher, trending-alert-bot) share the `src/` → `dist/` path plus `rolldown.config.ts`, and they store env/database samples beside the code for zero-dependency bundles. Python services (telegram-forwarder, telegram-watcher) keep orchestration in `core/`, adapters in `services/`, and routing data in `forward_rules.example.json`; create per-app venvs. Root configs (`package.json`, `pnpm-workspace.yaml`, `tsconfig.json`) define shared tooling, while `scripts/create-project.ts` (`pnpm new`) scaffolds new work.

## Build, Test & Development Commands
Install shared dependencies with `pnpm install`. For TypeScript work, run `pnpm --filter <app> dev` for vite-node hot reload, `pnpm --filter <app> build` for rolldown bundles, and `pnpm --filter <app> start:prod` to execute the emitted `dist/index.cjs`. Python bots should create a local env (`python -m venv venv && source venv/bin/activate`), install `pip install -r requirements.txt`, and start with `python main.py`.

## Coding Style & Naming Conventions
Respect the strict TS compiler options; run `pnpm exec eslint apps/<app>/src --max-warnings=0` and `pnpm exec prettier --check "apps/<app>/src/**/*.ts"` before committing. Prefer 2-space indentation, single quotes, and descriptive folders (`utils/`, `filters/`, `services/`). Python modules stay PEP 8 compliant, format with Black, and keep filenames snake_case while classes remain PascalCase.

## Testing Guidelines
Add Vitest suites next to the code (`src/__tests__/bot.test.ts`) and execute them via `pnpm --filter <app> vitest run` or `vitest watch` while iterating. Utility senders such as `pnpm --filter twitter-bot test:send` double as integration checks after messaging edits. Python services should provide smoke coverage inside `cli/` or `utils/`; when pytest modules exist, run `python -m pytest`, otherwise document manual verifications and capture sanitized logs. Cover happy paths and failure handling before submitting work.

## Commit & Pull Request Guidelines
Commits follow Conventional Commits (`feat`, `fix`, `chore`, `refactor`) and normally focus on a single app or script. Branch names should begin with `experiment/` or `fix/` plus a concise subject. Every PR needs a short description, linked issue or task, reproduced test commands (pnpm, python, curl payloads), and a list of config or data updates (`.env`, `forward_rules.json`, `db.json`). Screenshot bot dialogs or terminal output whenever behavior changes.

## Security & Configuration Tips
Only commit `.example` files for secrets, rule sets, and session state; real `.env`, Telegram sessions, and `forward_rules.json` stay local and ignored. Rotate API tokens, redact chat IDs or wallet addresses before sharing logs, and run `pnpm audit` or `pip list --outdated` after dependency bumps. Document new environment variables in the relevant README and PR checklist.

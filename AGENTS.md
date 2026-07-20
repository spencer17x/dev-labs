# Repository Guidelines

## Project Structure

- `apps/` contains the runnable applications.
- `apps/twitter-bot` is a bundled TypeScript service: source lives in `src/`, Rolldown emits `dist/index.cjs`, and local configuration is based on committed `.example` files.
- `apps/signal-trade` is the Next.js exception. App Router code lives in `app/`, UI in `components/`, browser orchestration in `hooks/`, and shared data/ingest logic in `lib/` and `lib/ingest/`. It no longer has a server-side runtime CLI or watcher.
- `apps/telegram-forwarder`, `apps/telegram-watcher`, and `apps/trending-alert-bot` are Python 3.11 applications. Each owns its `pyproject.toml`, `uv.lock`, local `.venv`, configuration samples, and `main.py` entry point.
- Root workspace configuration lives in `package.json`, `pnpm-workspace.yaml`, and `tsconfig.json`. `scripts/create-project.ts` powers `pnpm new`; `scripts/release/` contains release automation.

## Setup, Build, and Run Commands

Use the versions pinned by the repository: Node.js `22.11.0`, pnpm `10.33.0`, and Python `3.11.15`.

```bash
pnpm install
pnpm new
pnpm --filter twitter-bot dev
pnpm --filter twitter-bot build
pnpm --filter twitter-bot start:prod
pnpm --filter signal-trade dev
pnpm --filter signal-trade build
pnpm --filter signal-trade start
pnpm --filter signal-trade type-check
```

For a Python app, work from that app's directory:

```bash
uv python install
uv sync --locked
uv run python main.py
```

Some CLIs require an argument; for example, use `uv run python main.py bsc --dry-run` in `trending-alert-bot`.

## Testing and Code Style

- Keep TypeScript strict, use 2-space indentation and single quotes, and follow the existing local module layout.
- Keep TypeScript tests beside the code as `*.test.ts` or `*.test.tsx`. Run Signal Trade tests with `pnpm exec vitest run apps/signal-trade` and type-check with its package script.
- Follow PEP 8 for Python. Use `snake_case` for modules/functions and `PascalCase` for classes.
- Python tests live under each app's `tests/`; run `uv run python -m unittest discover -s tests` from the app directory.
- Validate only the affected app when possible, then broaden checks for shared workspace or release-script changes.

## Security and Configuration

Commit only sample configuration such as `.env.example`, `*.example.json`, or equivalent templates. Never commit real credentials, Telegram session files, local databases, logs, or runtime data. Redact chat IDs, wallet addresses, tokens, and message content from shared output. Document every new environment variable in the affected app's README and sample config.

## Commits, Pull Requests, and Releases

Follow the topic-specific rules in `.github/instructions/`:

- `coding.instructions.md` — formatting, testing, and security
- `commit.instructions.md` — Conventional Commits, branch names, and PR checklist
- `release.instructions.md` — directory-scoped automated releases

Do not create release tags manually. Release workflows derive app versions from commits touching `apps/<app>`.

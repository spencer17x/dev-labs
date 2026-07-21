# Coding Style Rules

## TypeScript

- Respect strict TS compiler options
- Format supported files with Prettier; the pre-commit hook checks the staged snapshot
- Run `pnpm --filter signal-trade type-check`, `pnpm --filter signal-trade test`, and the affected app build before pushing
- 2-space indentation, single quotes
- Descriptive folders: `utils/`, `filters/`, `services/`

## Python

- Keep code PEP 8 compliant
- Filenames: `snake_case`
- Classes: `PascalCase`
- Use the repo-root `.python-version`; install each app with `uv sync --locked`

## Testing

- TypeScript: keep `node:test` suites beside code as `*.test.ts` or `*.test.tsx`; execute them through vite-node
- Python: keep unittest suites under `tests/` and run `uv run python -m unittest discover -s tests`
- Cover happy paths and failure handling before submitting work

## Security & Configuration

- Only commit `.example` files for secrets, rule sets, and session state
- Real `.env`, Telegram sessions, and `forward_rules.json` stay local and git-ignored
- Redact chat IDs or wallet addresses before sharing logs
- Run `pnpm audit` or `uv pip list --outdated` after dependency bumps
- Document new environment variables in the relevant README and PR checklist

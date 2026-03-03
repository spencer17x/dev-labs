# Coding Style Rules

## TypeScript

- Respect strict TS compiler options
- Run `pnpm exec eslint apps/<app>/src --max-warnings=0` and `pnpm exec prettier --check "apps/<app>/src/**/*.ts"` before committing
- 2-space indentation, single quotes
- Descriptive folders: `utils/`, `filters/`, `services/`

## Python

- PEP 8 compliant, format with Black
- Filenames: `snake_case`
- Classes: `PascalCase`

## Testing

- TypeScript: add Vitest suites next to code (`src/__tests__/bot.test.ts`), run via `pnpm --filter <app> vitest run`
- Python: provide smoke coverage inside `cli/` or `utils/`; when pytest modules exist, run `python -m pytest`
- Cover happy paths and failure handling before submitting work

## Security & Configuration

- Only commit `.example` files for secrets, rule sets, and session state
- Real `.env`, Telegram sessions, and `forward_rules.json` stay local and git-ignored
- Redact chat IDs or wallet addresses before sharing logs
- Run `pnpm audit` or `pip list --outdated` after dependency bumps
- Document new environment variables in the relevant README and PR checklist

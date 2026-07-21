# Commit Message Rules

Every non-merge commit follows Conventional Commits and contains one subject line only:

```text
<type>(<scope>)!: <description>
```

`scope` and `!` are optional in the syntax. Commit bodies and footers are not allowed.

## Types

| Type       | Use for                                                  |
| ---------- | -------------------------------------------------------- |
| `feat`     | New user-visible behavior; produces a minor release bump |
| `fix`      | Bug fixes                                                |
| `chore`    | Maintenance that does not fit another type               |
| `refactor` | Internal restructuring without behavior changes          |
| `docs`     | Documentation only                                       |
| `style`    | Formatting or other non-functional code style changes    |
| `test`     | Test additions or corrections                            |
| `perf`     | Performance improvements                                 |
| `build`    | Build tooling or build dependency changes                |
| `ci`       | GitHub Actions and CI automation                         |
| `revert`   | Reverting an earlier commit                              |

Use `!` immediately before `:` for breaking changes. Because messages are title-only, do not use a `BREAKING CHANGE:` footer.

## Scope

- A commit whose files are all under one `apps/<app>` directory must use that exact app directory name as its scope.
- Root-only and cross-app commits may omit scope. If they use one, keep it lowercase and limited to letters, numbers, `.`, `_`, `/`, or `-`.
- Do not use stale or invented app scopes. Current app scopes are `signal-trade`, `twitter-bot`, `telegram-forwarder`, `telegram-watcher`, and `trending-alert-bot`.

## Description

- Keep the entire subject at 72 characters or fewer.
- Start with a lowercase imperative verb.
- Describe what changed, not how it was implemented.
- Do not end with punctuation.

## Generating Commit Messages

Always inspect the actual staged diff (`git diff --cached`) before suggesting a message. Use the unstaged diff only when nothing is staged. Split unrelated work into separate commits.

Examples:

```text
feat(trending-alert-bot): add per-chat notification modes
fix(telegram-forwarder): handle empty forwarding rules
docs: clarify workspace setup
ci: add change-aware quality checks
refactor(twitter-bot)!: replace the subscription storage format
```

## Enforcement

- `.githooks/commit-msg` validates the local commit message and app-only scope.
- `.githooks/pre-push` validates all outgoing non-merge commits.
- `.github/workflows/conventional-commits.yml` validates pull-request and direct-push commit ranges.
- Do not bypass hooks with `--no-verify` for review-bound work.

## Branch Naming

Branch names begin with `experiment/` or `fix/` followed by a concise kebab-case subject.

## Pull Request Checklist

Every PR includes:

- A short description and linked issue or task
- The exact test commands run
- Any configuration or data-shape changes
- Screenshots or terminal output when behavior changes

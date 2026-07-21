#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${repo_root}" ]]; then
  echo "[hooks] not inside a Git worktree; skipping installation"
  exit 0
fi

cd "${repo_root}"
git config --local core.hooksPath .githooks

echo "[hooks] installed pre-commit, commit-msg, and pre-push from .githooks/"

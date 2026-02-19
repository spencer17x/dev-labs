#!/usr/bin/env bash
set -euo pipefail

BASE_SHA="${1:-}"
HEAD_SHA="${2:-}"

if [[ -z "${BASE_SHA}" || -z "${HEAD_SHA}" ]]; then
  echo "Usage: $0 <base_sha> <head_sha>" >&2
  exit 2
fi

messages="$(git log --format=%s "${BASE_SHA}..${HEAD_SHA}" || true)"
if [[ -z "${messages}" ]]; then
  echo "No commits found in range ${BASE_SHA}..${HEAD_SHA}."
  exit 0
fi

# Conventional Commits:
# type(scope)!: subject
# type!: subject
# type: subject
pattern='^(feat|fix|chore|refactor|docs|style|test|perf|build|ci|revert)(\([a-z0-9._/-]+\))?(!)?: .+'

invalid=0
while IFS= read -r msg; do
  if [[ "${msg}" =~ ^Merge\  ]]; then
    continue
  fi
  if [[ ! "${msg}" =~ ${pattern} ]]; then
    echo "Invalid commit message: ${msg}"
    invalid=1
  fi
done <<< "${messages}"

if [[ "${invalid}" -ne 0 ]]; then
  echo ""
  echo "Expected format: type(scope): subject"
  echo "Examples: feat(bot): add /mode command, fix: guard null response"
  exit 1
fi

echo "All commit messages are valid."

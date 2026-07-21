#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <message-file> [--staged | --commit <sha> | --no-scope-check]" >&2
  exit 2
}

message_file="${1:-}"
mode="${2:---no-scope-check}"
commit_sha="${3:-}"
if [[ -z "${message_file}" || ! -r "${message_file}" ]]; then
  usage
fi
if [[ "${mode}" != "--staged" && "${mode}" != "--commit" && "${mode}" != "--no-scope-check" ]]; then
  usage
fi
if [[ "${mode}" == "--commit" && -z "${commit_sha}" ]]; then
  usage
fi

message="$(git stripspace --strip-comments <"${message_file}")"
subject="$(printf '%s\n' "${message}" | sed -n '1p')"

fail() {
  echo "[commit-msg] $1" >&2
  echo "[commit-msg] expected: type(scope)!: lowercase imperative description" >&2
  echo "[commit-msg] example: fix(signal-trade): handle empty feed response" >&2
  exit 1
}

if [[ -z "${subject}" ]]; then
  fail "commit message is empty"
fi

if [[ "${subject}" == Merge\ * ]]; then
  if [[ "${mode}" == "--staged" ]] && git rev-parse --verify --quiet MERGE_HEAD >/dev/null; then
    exit 0
  fi
  fail "Merge subjects are reserved for real merge commits"
fi

nonempty_lines="$(printf '%s\n' "${message}" | awk 'NF { count++ } END { print count + 0 }')"
if [[ "${nonempty_lines}" -ne 1 ]]; then
  fail "use one subject line only; bodies and footers are not allowed"
fi

if [[ "${#subject}" -gt 72 ]]; then
  fail "subject exceeds 72 characters (${#subject})"
fi

pattern='^(feat|fix|chore|refactor|docs|style|test|perf|build|ci|revert)(\(([a-z0-9][a-z0-9._/-]*)\))?(!)?: (.+)$'
if [[ ! "${subject}" =~ ${pattern} ]]; then
  fail "invalid Conventional Commit subject: ${subject}"
fi

scope="${BASH_REMATCH[3]:-}"
description="${BASH_REMATCH[5]}"
if [[ ! "${description}" =~ ^[a-z0-9] ]]; then
  fail "description must start with a lowercase ASCII letter or number"
fi
if [[ "${description}" =~ [.!?。！？]$ ]]; then
  fail "description must not end with punctuation"
fi

if [[ "${mode}" != "--no-scope-check" ]]; then
  changed_files=()
  if [[ "${mode}" == "--staged" ]]; then
    while IFS= read -r -d '' file; do
      changed_files+=("${file}")
    done < <(git diff --cached --name-only --diff-filter=ACMRD -z)
  else
    while IFS= read -r file; do
      [[ -n "${file}" ]] && changed_files+=("${file}")
    done < <(git diff-tree --root --no-commit-id --name-only -r "${commit_sha}")
  fi

  app_names=()
  outside_apps=0
  for file in "${changed_files[@]}"; do
    if [[ "${file}" =~ ^apps/([^/]+)/ ]]; then
      candidate="${BASH_REMATCH[1]}"
      already_added=0
      for app in "${app_names[@]-}"; do
        if [[ "${app}" == "${candidate}" ]]; then
          already_added=1
          break
        fi
      done
      if [[ "${already_added}" -eq 0 ]]; then
        app_names+=("${candidate}")
      fi
    else
      outside_apps=1
    fi
  done

  if [[ "${#app_names[@]}" -eq 1 && "${outside_apps}" -eq 0 ]]; then
    expected_scope="${app_names[0]}"
    if [[ "${scope}" != "${expected_scope}" ]]; then
      fail "changes only affect apps/${expected_scope}; scope must be (${expected_scope})"
    fi
  fi
fi

echo "[commit-msg] valid: ${subject}"

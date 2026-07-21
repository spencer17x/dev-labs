#!/usr/bin/env bash
set -euo pipefail

base_sha="${1:-}"
head_sha="${2:-}"
if [[ -z "${base_sha}" || -z "${head_sha}" ]]; then
  echo "Usage: $0 <base_sha> <head_sha>" >&2
  exit 2
fi

if [[ "${base_sha}" =~ ^0+$ ]]; then
  revision="${head_sha}"
else
  revision="${base_sha}..${head_sha}"
fi

commits="$(git rev-list --reverse "${revision}" || true)"
if [[ -z "${commits}" ]]; then
  echo "[commit-range] no commits found in ${revision}"
  exit 0
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
message_file="$(mktemp)"
trap 'rm -f "${message_file}"' EXIT

invalid=0
while IFS= read -r commit_sha; do
  [[ -z "${commit_sha}" ]] && continue
  parent_count="$(git show -s --format=%P "${commit_sha}" | awk '{ print NF }')"
  if [[ "${parent_count}" -gt 1 ]]; then
    echo "[commit-range] skipping merge commit ${commit_sha}"
    continue
  fi

  git show -s --format=%B "${commit_sha}" >"${message_file}"
  if ! bash "${script_dir}/validate-commit-message.sh" "${message_file}" --commit "${commit_sha}"; then
    echo "[commit-range] invalid commit: ${commit_sha}" >&2
    invalid=1
  fi
done <<<"${commits}"

if [[ "${invalid}" -ne 0 ]]; then
  exit 1
fi

echo "[commit-range] all commit messages are valid"

#!/usr/bin/env bash
set -euo pipefail

test_root="${1:-}"
if [[ -z "${test_root}" || ! -d "${test_root}" ]]; then
  echo "Usage: $0 <test-root>" >&2
  exit 2
fi

repo_root="$(git rev-parse --show-toplevel)"
runner="${repo_root}/node_modules/.bin/vite-node"
if [[ ! -x "${runner}" ]]; then
  echo "vite-node is unavailable; run pnpm install first" >&2
  exit 1
fi

test_files=()
while IFS= read -r file; do
  test_files+=("${file}")
done < <(find "${test_root}" -type f \( -name '*.test.ts' -o -name '*.test.tsx' \) -print | LC_ALL=C sort)

if [[ "${#test_files[@]}" -eq 0 ]]; then
  echo "No TypeScript test files found under ${test_root}" >&2
  exit 1
fi

failed=0
for file in "${test_files[@]}"; do
  echo "[node-test] ${file}"
  if ! "${runner}" "${file}"; then
    failed=1
  fi
done

exit "${failed}"

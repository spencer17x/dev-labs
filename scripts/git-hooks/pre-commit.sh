#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "${repo_root}"

staged_files=()
while IFS= read -r -d '' file; do
  staged_files+=("${file}")
done < <(git diff --cached --name-only --diff-filter=ACMR -z)

if [[ "${#staged_files[@]}" -eq 0 ]]; then
  exit 0
fi

echo "[pre-commit] checking staged changes"
git diff --cached --check

invalid_added=0
while IFS= read -r -d '' file; do
  if git check-ignore --quiet --no-index -- "${file}"; then
    echo "[pre-commit] ignored file must not be committed: ${file}" >&2
    invalid_added=1
  fi
done < <(git diff --cached --name-only --diff-filter=A -z)

if [[ "${invalid_added}" -ne 0 ]]; then
  exit 1
fi

syntax_failed=0
format_files=()
python_runner=""
for file in "${staged_files[@]}"; do
  case "${file}" in
    *.sh|.githooks/*)
      if ! git show ":${file}" | bash -n; then
        echo "[pre-commit] invalid Bash syntax: ${file}" >&2
        syntax_failed=1
      fi
      ;;
    *.py)
      if [[ -z "${python_runner}" ]]; then
        if command -v uv >/dev/null 2>&1; then
          python_runner="$(uv python find 3.11.15 2>/dev/null || true)"
        elif command -v python3 >/dev/null 2>&1 && \
          [[ "$(python3 -c 'import platform; print(platform.python_version())')" == "3.11.15" ]]; then
          python_runner="$(command -v python3)"
        fi
      fi
      if [[ -z "${python_runner}" ]]; then
        echo "[pre-commit] Python 3.11.15 is required; run uv python install 3.11.15" >&2
        syntax_failed=1
      elif ! git show ":${file}" | "${python_runner}" -c \
        'import sys; compile(sys.stdin.read(), sys.argv[1], "exec")' "${file}"; then
        echo "[pre-commit] invalid Python syntax: ${file}" >&2
        syntax_failed=1
      fi
      ;;
  esac

  case "${file}" in
    pnpm-lock.yaml|*/uv.lock)
      ;;
    *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs|*.json|*.jsonc|*.md|*.mdx|*.yml|*.yaml|*.css)
      format_files+=("${file}")
      ;;
  esac
done

if [[ "${syntax_failed}" -ne 0 ]]; then
  exit 1
fi

if [[ "${#format_files[@]}" -gt 0 ]]; then
  prettier="${repo_root}/node_modules/.bin/prettier"
  if [[ ! -x "${prettier}" ]]; then
    echo "[pre-commit] Prettier is unavailable; run pnpm install first" >&2
    exit 1
  fi

  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "${tmp_dir}"' EXIT
  format_failed=0
  index=0
  for file in "${format_files[@]}"; do
    index=$((index + 1))
    staged_file="${tmp_dir}/${index}.staged"
    formatted_file="${tmp_dir}/${index}.formatted"
    git show ":${file}" >"${staged_file}"
    "${prettier}" --stdin-filepath "${file}" <"${staged_file}" >"${formatted_file}"
    if ! diff -u "${staged_file}" "${formatted_file}"; then
      echo "[pre-commit] format with: pnpm exec prettier --write \"${file}\"" >&2
      format_failed=1
    fi
  done

  if [[ "${format_failed}" -ne 0 ]]; then
    exit 1
  fi
fi

echo "[pre-commit] passed"

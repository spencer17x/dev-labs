#!/usr/bin/env bash
set -euo pipefail

base_sha="${1:-}"
head_sha="${2:-HEAD}"
if [[ -z "${base_sha}" ]]; then
  echo "Usage: $0 <base_sha> [head_sha]" >&2
  exit 2
fi

repo_root="$(git rev-parse --show-toplevel)"
cd "${repo_root}"

if ! git cat-file -e "${head_sha}^{commit}" 2>/dev/null; then
  echo "[quality] head revision is not a commit: ${head_sha}" >&2
  exit 2
fi

empty_tree="$(git hash-object -t tree /dev/null)"
if [[ "${base_sha}" =~ ^0+$ ]] || ! git cat-file -e "${base_sha}^{commit}" 2>/dev/null; then
  diff_base="${empty_tree}"
else
  diff_base="${base_sha}"
fi

changed_files=()
while IFS= read -r -d '' file; do
  changed_files+=("${file}")
done < <(git diff --name-only --diff-filter=ACMR -z "${diff_base}" "${head_sha}")

if [[ "${#changed_files[@]}" -eq 0 ]]; then
  echo "[quality] no changed files"
  exit 0
fi

echo "[quality] checking ${#changed_files[@]} changed files"
git diff --check "${diff_base}" "${head_sha}"

run_root_types=0
run_signal_trade=0
run_twitter_bot=0
run_telegram_forwarder=0
run_telegram_watcher=0
run_trending_alert_bot=0
run_all=0
format_files=()

for file in "${changed_files[@]}"; do
  case "${file}" in
    scripts/ci/*|.github/workflows/quality.yml)
      run_all=1
      ;;
    package.json|pnpm-lock.yaml|pnpm-workspace.yaml|tsconfig.json|tsconfig.*.json)
      run_root_types=1
      run_signal_trade=1
      run_twitter_bot=1
      ;;
    .python-version)
      run_telegram_forwarder=1
      run_telegram_watcher=1
      run_trending_alert_bot=1
      ;;
    scripts/*.ts|scripts/**/*.ts)
      run_root_types=1
      ;;
    apps/signal-trade/*)
      run_signal_trade=1
      ;;
    apps/twitter-bot/*)
      run_twitter_bot=1
      ;;
    apps/telegram-forwarder/*)
      run_telegram_forwarder=1
      ;;
    apps/telegram-watcher/*)
      run_telegram_watcher=1
      ;;
    apps/trending-alert-bot/*)
      run_trending_alert_bot=1
      ;;
  esac

  case "${file}" in
    pnpm-lock.yaml|*/uv.lock)
      ;;
    *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs|*.json|*.jsonc|*.md|*.mdx|*.yml|*.yaml|*.css)
      format_files+=("${file}")
      ;;
  esac

  case "${file}" in
    *.sh|.githooks/*)
      if ! git show "${head_sha}:${file}" | bash -n; then
        echo "[quality] invalid Bash syntax: ${file}" >&2
        exit 1
      fi
      ;;
  esac
done

if [[ "${run_all}" -eq 1 ]]; then
  run_root_types=1
  run_signal_trade=1
  run_twitter_bot=1
  run_telegram_forwarder=1
  run_telegram_watcher=1
  run_trending_alert_bot=1
fi

if [[ "${#format_files[@]}" -gt 0 ]]; then
  prettier="${repo_root}/node_modules/.bin/prettier"
  if [[ ! -x "${prettier}" ]]; then
    echo "[quality] Prettier is unavailable; run pnpm install first" >&2
    exit 1
  fi

  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "${tmp_dir}"' EXIT
  format_failed=0
  index=0
  for file in "${format_files[@]}"; do
    index=$((index + 1))
    source_file="${tmp_dir}/${index}.source"
    formatted_file="${tmp_dir}/${index}.formatted"
    git show "${head_sha}:${file}" >"${source_file}"
    "${prettier}" --stdin-filepath "${file}" <"${source_file}" >"${formatted_file}"
    if ! diff -u "${source_file}" "${formatted_file}"; then
      echo "[quality] formatting failed for ${file}" >&2
      format_failed=1
    fi
  done
  if [[ "${format_failed}" -ne 0 ]]; then
    echo "[quality] run pnpm exec prettier --write on the files above" >&2
    exit 1
  fi
fi

needs_node=0
if [[ "${run_root_types}" -eq 1 || "${run_signal_trade}" -eq 1 || "${run_twitter_bot}" -eq 1 ]]; then
  needs_node=1
fi

if [[ "${needs_node}" -eq 1 ]]; then
  command -v node >/dev/null 2>&1 || { echo "[quality] node is required" >&2; exit 1; }
  direct_pnpm_version=""
  if command -v pnpm >/dev/null 2>&1; then
    direct_pnpm_version="$(pnpm --version 2>/dev/null || true)"
  fi
  if [[ "${direct_pnpm_version}" == "11.5.0" ]]; then
    pnpm_command=(pnpm)
    actual_pnpm="${direct_pnpm_version}"
  elif command -v corepack >/dev/null 2>&1; then
    pnpm_command=(corepack pnpm)
    actual_pnpm="$("${pnpm_command[@]}" --version)"
  else
    echo "[quality] pnpm 11.5.0 or Corepack is required" >&2
    exit 1
  fi
  actual_node="$(node -p 'process.versions.node')"
  if [[ "${actual_node}" != "24.16.0" || "${actual_pnpm}" != "11.5.0" ]]; then
    echo "[quality] expected Node 24.16.0 and pnpm 11.5.0" >&2
    echo "[quality] found Node ${actual_node} and pnpm ${actual_pnpm}" >&2
    exit 1
  fi
fi

if [[ "${run_root_types}" -eq 1 ]]; then
  echo "[quality] type-checking root TypeScript"
  "${pnpm_command[@]}" exec tsc --project tsconfig.scripts.json --pretty false
fi

if [[ "${run_signal_trade}" -eq 1 ]]; then
  echo "[quality] checking signal-trade"
  "${pnpm_command[@]}" --filter signal-trade type-check
  "${pnpm_command[@]}" --filter signal-trade test
  "${pnpm_command[@]}" --filter signal-trade build
fi

if [[ "${run_twitter_bot}" -eq 1 ]]; then
  echo "[quality] building twitter-bot"
  "${pnpm_command[@]}" --filter twitter-bot build
fi

run_python_app() {
  local app_dir="$1"
  command -v uv >/dev/null 2>&1 || { echo "[quality] uv is required" >&2; exit 1; }

  echo "[quality] checking ${app_dir}"
  (
    cd "${app_dir}"
    uv sync --locked --python 3.11.15
    python_version="$(uv run python -c 'import platform; print(platform.python_version())')"
    if [[ "${python_version}" != "3.11.15" ]]; then
      echo "[quality] expected Python 3.11.15, found ${python_version} in ${app_dir}" >&2
      exit 1
    fi
    uv run python -m compileall -q -x '(^|/)(\.venv|__pycache__|\.pytest_cache)(/|$)' .
    if find tests -type f -name 'test_*.py' -print -quit 2>/dev/null | grep -q .; then
      uv run python -m unittest discover -s tests
    fi
  )
}

if [[ "${run_telegram_forwarder}" -eq 1 ]]; then
  run_python_app apps/telegram-forwarder
fi
if [[ "${run_telegram_watcher}" -eq 1 ]]; then
  run_python_app apps/telegram-watcher
fi
if [[ "${run_trending_alert_bot}" -eq 1 ]]; then
  run_python_app apps/trending-alert-bot
fi

echo "[quality] all checks passed"

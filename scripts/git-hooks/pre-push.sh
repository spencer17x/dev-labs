#!/usr/bin/env bash
set -euo pipefail

remote_name="${1:-origin}"
repo_root="$(git rev-parse --show-toplevel)"
zero_sha="0000000000000000000000000000000000000000"
quality_script="${repo_root}/scripts/ci/validate-changes.sh"
commit_script="${repo_root}/scripts/quality/validate-commit-range.sh"

default_remote_ref="$(git symbolic-ref --quiet --short "refs/remotes/${remote_name}/HEAD" 2>/dev/null || true)"
if [[ -z "${default_remote_ref}" ]] && git show-ref --verify --quiet "refs/remotes/${remote_name}/main"; then
  default_remote_ref="${remote_name}/main"
fi

validated=0
while read -r local_ref local_sha remote_ref remote_sha; do
  [[ -z "${local_ref:-}" ]] && continue
  if [[ "${local_sha}" == "${zero_sha}" ]]; then
    continue
  fi

  if [[ "${remote_ref}" == refs/tags/*/v* ]]; then
    echo "[pre-push] app release tags are created by GitHub Actions; do not push ${remote_ref}" >&2
    exit 1
  fi
  if [[ "${local_ref}" != refs/heads/* ]]; then
    continue
  fi

  if [[ "${remote_sha}" != "${zero_sha}" ]]; then
    base_sha="${remote_sha}"
  elif [[ -n "${default_remote_ref}" ]]; then
    base_sha="$(git merge-base "${local_sha}" "${default_remote_ref}")"
  else
    base_sha="${zero_sha}"
  fi

  echo "[pre-push] validating ${local_ref} against ${base_sha}"
  bash "${commit_script}" "${base_sha}" "${local_sha}"
  bash "${quality_script}" "${base_sha}" "${local_sha}"
  validated=1
done

if [[ "${validated}" -eq 0 ]]; then
  echo "[pre-push] no branch updates require validation"
else
  echo "[pre-push] passed"
fi

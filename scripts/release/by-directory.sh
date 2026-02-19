#!/usr/bin/env bash
set -euo pipefail

DRY_RUN="${DRY_RUN:-false}"
DEFAULT_INITIAL_VERSION="${DEFAULT_INITIAL_VERSION:-0.1.0}"
CHANGED_APPS="${CHANGED_APPS:-}"

if [[ "${DRY_RUN}" != "true" && "${DRY_RUN}" != "false" ]]; then
  echo "DRY_RUN must be true or false" >&2
  exit 1
fi

if [[ ! -d apps ]]; then
  echo "apps directory not found" >&2
  exit 1
fi

if [[ "${DRY_RUN}" == "false" ]]; then
  if [[ -z "${GITHUB_TOKEN:-}" && -z "${GH_TOKEN:-}" ]]; then
    echo "GITHUB_TOKEN/GH_TOKEN is required for release creation" >&2
    exit 1
  fi
fi

semver_bump() {
  local version="$1"
  local bump="$2"
  local major minor patch
  IFS='.' read -r major minor patch <<<"${version}"

  case "${bump}" in
    major)
      major=$((major + 1))
      minor=0
      patch=0
      ;;
    minor)
      minor=$((minor + 1))
      patch=0
      ;;
    patch)
      patch=$((patch + 1))
      ;;
    *)
      echo "unknown bump type: ${bump}" >&2
      exit 1
      ;;
  esac

  echo "${major}.${minor}.${patch}"
}

latest_tag_for_app() {
  local app="$1"
  git tag --list "${app}/v*" --sort=-v:refname | head -n 1
}

has_breaking_changes() {
  local range="$1"
  local path="$2"

  if git log ${range} --pretty=format:'%s' -- "${path}" | grep -Eq '^[a-zA-Z]+(\(.+\))?!:'; then
    return 0
  fi

  if git log ${range} --pretty=format:'%b' -- "${path}" | grep -Eq 'BREAKING CHANGE:'; then
    return 0
  fi

  return 1
}

has_feat_changes() {
  local range="$1"
  local path="$2"
  git log ${range} --pretty=format:'%s' -- "${path}" | grep -Eq '^feat(\(.+\))?:'
}

commit_count_for_path() {
  local range="$1"
  local path="$2"
  git rev-list --count ${range} -- "${path}"
}

section_lines() {
  local range="$1"
  local path="$2"
  local pattern="$3"
  local repo_url="$4"

  git log ${range} --pretty=format:'%s|%h|%an' -- "${path}" \
    | grep -E "${pattern}" \
    | awk -F'|' -v repo_url="${repo_url}" '
      function pr_link(subject,  pr, link) {
        if (match(subject, /\(#[0-9]+\)$/)) {
          pr = substr(subject, RSTART + 2, RLENGTH - 3)
          if (repo_url != "") {
            link = sprintf(" [PR #%s](%s/pull/%s)", pr, repo_url, pr)
          } else {
            link = sprintf(" PR #%s", pr)
          }
          return link
        }
        return ""
      }
      {
        subject=$1
        hash=$2
        author=$3
        printf("- %s (%s) — %s%s\n", subject, hash, author, pr_link(subject))
      }
    ' \
    || true
}

make_notes_file() {
  local app="$1"
  local new_tag="$2"
  local previous_tag="$3"
  local range="$4"
  local path="$5"
  local file="$6"
  local repo_url="$7"

  {
    echo "# ${new_tag}"
    echo

    if [[ -n "${previous_tag}" ]]; then
      echo "Changes since ${previous_tag}."
    else
      echo "Initial release for ${app}."
    fi

    echo

    local features fixes refactors chores others breaking
    features="$(section_lines "${range}" "${path}" '^feat(\(.+\))?:' "${repo_url}")"
    fixes="$(section_lines "${range}" "${path}" '^fix(\(.+\))?:' "${repo_url}")"
    refactors="$(section_lines "${range}" "${path}" '^refactor(\(.+\))?:' "${repo_url}")"
    chores="$(section_lines "${range}" "${path}" '^chore(\(.+\))?:' "${repo_url}")"
    breaking="$(section_lines "${range}" "${path}" '^[a-zA-Z]+(\(.+\))?!:' "${repo_url}")"

    # others: non-empty commit subjects not matched above
    others="$(git log ${range} --pretty=format:'%s|%h|%an' -- "${path}" \
      | grep -Ev '^(feat|fix|refactor|chore|docs|test|ci|build|perf|style)(\(.+\))?!?:' \
      | awk -F'|' '{ printf("- %s (%s) — %s\n", $1, $2, $3) }' || true)"

    if [[ -n "${breaking}" ]]; then
      echo "## Breaking Changes"
      echo "${breaking}"
      echo
    fi

    if [[ -n "${features}" ]]; then
      echo "## Features"
      echo "${features}"
      echo
    fi

    if [[ -n "${fixes}" ]]; then
      echo "## Fixes"
      echo "${fixes}"
      echo
    fi

    if [[ -n "${refactors}" ]]; then
      echo "## Refactors"
      echo "${refactors}"
      echo
    fi

    if [[ -n "${chores}" ]]; then
      echo "## Chores"
      echo "${chores}"
      echo
    fi

    if [[ -n "${others}" ]]; then
      echo "## Others"
      echo "${others}"
      echo
    fi

    echo "## Full Changelog"
    if [[ -n "${previous_tag}" ]]; then
      echo "- ${previous_tag}...${new_tag}"
    else
      echo "- Initial release"
    fi
  } >"${file}"
}

create_release_for_app() {
  local app="$1"
  local path="apps/${app}"
  local latest_tag range commit_count bump current_version new_version new_tag notes_file
  local remote_url repo_url
  local gh_token

  latest_tag="$(latest_tag_for_app "${app}")"

  if [[ -n "${latest_tag}" ]]; then
    range="${latest_tag}..HEAD"
  else
    range="HEAD"
  fi

  commit_count="$(commit_count_for_path "${range}" "${path}")"
  if [[ "${commit_count}" == "0" ]]; then
    echo "[skip] ${app}: no changes"
    return
  fi

  if has_breaking_changes "${range}" "${path}"; then
    bump="major"
  elif has_feat_changes "${range}" "${path}"; then
    bump="minor"
  else
    bump="patch"
  fi

  if [[ -n "${latest_tag}" ]]; then
    current_version="${latest_tag#${app}/v}"
  else
    current_version="${DEFAULT_INITIAL_VERSION}"
    # for first release, do not bump again if default initial is desired target
    bump="none"
  fi

  if [[ "${bump}" == "none" ]]; then
    new_version="${current_version}"
  else
    new_version="$(semver_bump "${current_version}" "${bump}")"
  fi

  new_tag="${app}/v${new_version}"

  if git rev-parse "refs/tags/${new_tag}" >/dev/null 2>&1; then
    echo "[skip] ${app}: tag ${new_tag} already exists"
    return
  fi

  if git ls-remote --exit-code --tags origin "refs/tags/${new_tag}" >/dev/null 2>&1; then
    echo "[skip] ${app}: remote tag ${new_tag} already exists"
    return
  fi

  remote_url="$(git config --get remote.origin.url || true)"
  repo_url=""
  if [[ "${remote_url}" =~ ^git@github.com:(.+)\.git$ ]]; then
    repo_url="https://github.com/${BASH_REMATCH[1]}"
  elif [[ "${remote_url}" =~ ^https://github.com/(.+)\.git$ ]]; then
    repo_url="https://github.com/${BASH_REMATCH[1]}"
  elif [[ "${remote_url}" =~ ^https://github.com/(.+)$ ]]; then
    repo_url="https://github.com/${BASH_REMATCH[1]}"
  fi

  notes_file="$(mktemp)"
  make_notes_file "${app}" "${new_tag}" "${latest_tag}" "${range}" "${path}" "${notes_file}" "${repo_url}"

  echo "[release] ${app}: ${new_tag} (${bump}, commits=${commit_count})"

  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "[dry-run] would create tag + release for ${new_tag}"
    sed -n '1,80p' "${notes_file}"
    rm -f "${notes_file}"
    return
  fi

  gh_token="${GH_TOKEN:-${GITHUB_TOKEN:-}}"

  git tag "${new_tag}" "${GITHUB_SHA:-HEAD}"
  if ! git push origin "${new_tag}"; then
    if git ls-remote --exit-code --tags origin "refs/tags/${new_tag}" >/dev/null 2>&1; then
      echo "[skip] ${app}: remote tag ${new_tag} created by another run"
      rm -f "${notes_file}"
      return
    fi
    echo "[error] ${app}: failed to push tag ${new_tag}" >&2
    rm -f "${notes_file}"
    exit 1
  fi

  if GH_TOKEN="${gh_token}" gh release view "${new_tag}" >/dev/null 2>&1; then
    echo "[skip] ${app}: release ${new_tag} already exists"
    rm -f "${notes_file}"
    return
  fi

  GH_TOKEN="${gh_token}" gh release create "${new_tag}" --title "${new_tag}" --notes-file "${notes_file}"

  rm -f "${notes_file}"
}

main() {
  apps=()
  while IFS= read -r app; do
    apps+=("${app}")
  done < <(find apps -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort)

  if [[ -n "${CHANGED_APPS}" ]]; then
    selected=()
    IFS=',' read -r -a requested_apps <<< "${CHANGED_APPS}"
    for app in "${apps[@]}"; do
      for requested in "${requested_apps[@]}"; do
        if [[ "${app}" == "${requested}" ]]; then
          selected+=("${app}")
          break
        fi
      done
    done

    apps=()
    for app in "${selected[@]-}"; do
      if [[ -n "${app}" ]]; then
        apps+=("${app}")
      fi
    done
  fi

  if [[ "${#apps[@]}" -eq 0 ]]; then
    if [[ -n "${CHANGED_APPS}" ]]; then
      echo "No matched apps for CHANGED_APPS=${CHANGED_APPS}"
    else
      echo "No apps found under ./apps"
    fi
    exit 0
  fi

  for app in "${apps[@]}"; do
    create_release_for_app "${app}"
  done
}

main "$@"

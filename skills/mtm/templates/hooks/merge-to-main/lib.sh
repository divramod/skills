# managed by /mtm config: the merge-to-main hooks' dispatcher and helpers.
#
# hal2-cli-git runs .hal/hooks/merge-to-main/<phase>.sh; each of them only
# calls hal_run_parts, which runs parts/<part>/<phase>.sh of every part (an
# app, or a workspace several apps share) in name order, from the checkout
# the phase runs in (the worktree for worktree-pre-merge, the main checkout
# for main-*). A part script is sourced by `bash -euo pipefail` with these
# helpers loaded, and HAL_PHASE, HAL_PART, HAL_PART_DIR set:
#
#   hal_skip_unless_changed [<pathspec>...]  exit 0 unless the part's files changed
#   hal_changed [<pathspec>...]              did the part's files change in this landing?
#   hal_changed_since <commit> [<pathspec>...]  ... since <commit> (e.g. what an installed build was built from)
#   hal_log <message>                        print "<phase>[<part>]: <message>"
#
# The part's files are the pathspecs in parts/<part>/paths (one per line,
# `#` comments); extra pathspecs narrow them (`':(exclude,glob)**/Tests/**'`).
# "Changed" means: the branch's changes (worktree-pre-merge), the staged
# merge (main-pre-commit), the merge commit (main-post-commit).
#
# A failing part stops worktree-pre-merge and main-pre-commit (the landing
# stops, main stays unchanged); in main-post-commit the other parts still
# run and the hook fails at the end (the landing stays, hal2-cli-git warns).
# HAL_HOOK_FORCE_CHANGED=1 counts every part as changed and HAL_HOOK_ONLY_PART
# (comma separated) runs only those parts: for trying hooks out.
# Written for bash 3.2 (macOS's /bin/bash) too.

HAL_HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

hal_log() {
  echo "${HAL_PHASE:-hook}[${HAL_PART:-}]: $*"
}

# The part's pathspecs into HAL_PATHS; a missing or empty paths file is a
# configuration error that fails the part.
hal_paths() {
  local file="$HAL_PART_DIR/paths" line
  HAL_PATHS=()
  if [[ ! -f "$file" ]]; then
    hal_log "no paths file ($file)" >&2
    exit 2
  fi
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    [[ -z "$line" || "$line" == \#* ]] && continue
    HAL_PATHS+=("$line")
  done <"$file"
  if [[ ${#HAL_PATHS[@]} -eq 0 ]]; then
    hal_log "paths file lists no pathspec ($file)" >&2
    exit 2
  fi
}

# origin/<default branch> when it exists, else the local branch.
hal_default_ref() {
  local branch="${HAL_HOOK_DEFAULT_BRANCH:-main}"
  if git rev-parse --verify --quiet "origin/$branch^{commit}" >/dev/null; then
    echo "origin/$branch"
  else
    echo "$branch"
  fi
}

# A git error counts as changed (`!` of a non-0/1 exit), so checks rather run
# once too often than never.
hal_changed() {
  [[ "${HAL_HOOK_FORCE_CHANGED:-}" == 1 ]] && return 0
  hal_paths
  case "$HAL_PHASE" in
    worktree-pre-merge)
      local base
      base="$(git merge-base HEAD "$(hal_default_ref)" 2>/dev/null)" || return 0
      ! git diff --quiet "$base" HEAD -- "${HAL_PATHS[@]}" "$@"
      ;;
    main-pre-commit) ! git diff --cached --quiet HEAD -- "${HAL_PATHS[@]}" "$@" ;;
    main-post-commit) ! git diff --quiet HEAD^1 HEAD -- "${HAL_PATHS[@]}" "$@" ;;
    *) return 0 ;;
  esac
}

hal_changed_since() {
  local since="$1"
  shift
  [[ "${HAL_HOOK_FORCE_CHANGED:-}" == 1 ]] && return 0
  hal_paths
  git cat-file -e "$since^{commit}" 2>/dev/null || return 0
  ! git diff --quiet "$since" HEAD -- "${HAL_PATHS[@]}" "$@"
}

hal_skip_unless_changed() {
  if ! hal_changed "$@"; then
    hal_log "unchanged, skipped"
    exit 0
  fi
}

hal_run_parts() {
  local phase="$1" root dir part script code failed=""
  case "$phase" in
    worktree-pre-merge) root="${HAL_HOOK_WORKTREE:-}" ;;
    *) root="${HAL_HOOK_MAIN_ROOT:-}" ;;
  esac
  root="${root:-$(git rev-parse --show-toplevel)}"
  for dir in "$HAL_HOOKS_DIR"/parts/*/; do
    part="$(basename "$dir")"
    script="$dir$phase.sh"
    [[ -f "$script" ]] || continue
    if [[ -n "${HAL_HOOK_ONLY_PART:-}" && ",$HAL_HOOK_ONLY_PART," != *",$part,"* ]]; then
      continue
    fi
    echo "$phase[$part]: running"
    code=0
    (
      cd "$root" &&
        HAL_PHASE="$phase" HAL_PART="$part" HAL_PART_DIR="${dir%/}" \
          bash -euo pipefail -c 'source "$1"; source "$2"' _ "$HAL_HOOKS_DIR/lib.sh" "$script"
    ) || code=$?
    if [[ $code -ne 0 ]]; then
      echo "$phase[$part]: failed with exit code $code" >&2
      [[ "$phase" == main-post-commit ]] || exit "$code"
      failed="$failed $part"
    fi
  done
  if [[ -n "$failed" ]]; then
    echo "$phase: failed parts:$failed" >&2
    exit 1
  fi
}

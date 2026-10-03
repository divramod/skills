#!/usr/bin/env bash
# The owner skill: after every landing, main flows into the owner slot, so the owner reads the
# latest main right away. Never fails a delivery: a merge that cannot happen now waits for the
# owner's next round (it merges main every round too).
set -uo pipefail
owner="${HAL_OWNER_BRANCH:-owner}"
dir="$(git -C "${HAL_HOOK_MAIN_ROOT:-.}" worktree list --porcelain \
  | awk -v b="branch refs/heads/$owner" '/^worktree /{w=substr($0,10)} $0==b{print w}')"
[ -n "$dir" ] || exit 0
default="${HAL_HOOK_DEFAULT_BRANCH:-main}"
if git -C "$dir" merge --no-edit "$default" >/dev/null 2>&1; then
  echo "owner: merged $default into $dir"
else
  git -C "$dir" merge --abort >/dev/null 2>&1 || true
  echo "owner: could not merge $default into $dir now; the owner's next round will" >&2
fi
exit 0

#!/usr/bin/env bash
# The farmer skill: after every landing, main flows into the farmer slot, so the farmer reads the
# latest main right away. Never fails a delivery: a merge that cannot happen now waits for the
# farmer's next round (it merges main every round too).
set -uo pipefail
farmer="${HAL_FARMER_BRANCH:-farmer}"
dir="$(git -C "${HAL_HOOK_MAIN_ROOT:-.}" worktree list --porcelain \
  | awk -v b="branch refs/heads/$farmer" '/^worktree /{w=substr($0,10)} $0==b{print w}')"
[ -n "$dir" ] || exit 0
default="${HAL_HOOK_DEFAULT_BRANCH:-main}"
if git -C "$dir" merge --no-edit "$default" >/dev/null 2>&1; then
  echo "farmer: merged $default into $dir"
else
  git -C "$dir" merge --abort >/dev/null 2>&1 || true
  echo "farmer: could not merge $default into $dir now; the farmer's next round will" >&2
fi
exit 0

#!/usr/bin/env bash
# The farmer skill: every landing carries the farmer branch's FARMER-ROLE.md commits to main.
# Runs in the worktree being landed, after main was merged in and the gates passed. The farmer
# branch may only change FARMER-ROLE.md; anything else is not merged (it would skip the gates).
set -euo pipefail
farmer="${HAL_FARMER_BRANCH:-farmer}"
[ "${HAL_HOOK_BRANCH:-}" = "$farmer" ] && exit 0
git rev-parse --verify --quiet "refs/heads/$farmer" >/dev/null || exit 0
[ -n "$(git rev-list HEAD.."$farmer")" ] || exit 0
changed="$(git diff --name-only HEAD..."$farmer")"
if [ -n "$(printf '%s\n' "$changed" | grep -vx 'FARMER-ROLE.md' | grep -v '^$' || true)" ]; then
  echo "farmer: branch $farmer changes more than FARMER-ROLE.md; not merged into this landing:" >&2
  printf '  %s\n' $changed >&2
  exit 0
fi
git merge --no-edit -m "Merge branch '$farmer' (FARMER-ROLE.md) into $HAL_HOOK_BRANCH" "$farmer"
echo "farmer: merged $farmer's FARMER-ROLE.md into this landing"

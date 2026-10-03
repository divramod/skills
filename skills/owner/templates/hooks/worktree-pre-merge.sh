#!/usr/bin/env bash
# The owner skill: every landing carries the owner branch's OWNER-ROLE.md commits to main.
# Runs in the worktree being landed, after main was merged in and the gates passed. The owner
# branch may only change OWNER-ROLE.md; anything else is not merged (it would skip the gates).
set -euo pipefail
owner="${HAL_OWNER_BRANCH:-owner}"
[ "${HAL_HOOK_BRANCH:-}" = "$owner" ] && exit 0
git rev-parse --verify --quiet "refs/heads/$owner" >/dev/null || exit 0
[ -n "$(git rev-list HEAD.."$owner")" ] || exit 0
changed="$(git diff --name-only HEAD..."$owner")"
if [ -n "$(printf '%s\n' "$changed" | grep -vx 'OWNER-ROLE.md' | grep -v '^$' || true)" ]; then
  echo "owner: branch $owner changes more than OWNER-ROLE.md; not merged into this landing:" >&2
  printf '  %s\n' $changed >&2
  exit 0
fi
git merge --no-edit -m "Merge branch '$owner' (OWNER-ROLE.md) into $HAL_HOOK_BRANCH" "$owner"
echo "owner: merged $owner's OWNER-ROLE.md into this landing"

#!/usr/bin/env bash
# Plan 0008 step 4: a servant slot with a farmer `decision` entry absent from its plan gets it back after /handoff c.
# Scratch only: a farmer repo `hal2` (its state in a temp FARMER_DIR) and a servant worktree `skills/04` whose
# HANDOFF.md names the farmer. Runs the Continue step's scripts the way the skill text says, the model's part (writing
# the returned decision into the plan) done by sed.
set -euo pipefail
for t in git python3; do command -v "$t" >/dev/null || { echo "dry-run.sh: $t is missing" >&2; exit 2; }; done

here="$(cd "$(dirname "$0")" && pwd)"
skills="$(cd "$here/../../skills" && pwd)"
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
export FARMER_DIR="$T/state" HAL2_WORKTREE_ROOT="$T/wt"
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t

repo() {  # repo <main dir> <slot>: a main checkout with one worktree slot under $T/wt/<name>/<slot>
  git init -q -b main "$1" && git -C "$1" commit -q --allow-empty -m init
  git -C "$1" worktree add -q -b "$2" "$T/wt/$(basename "$1")/$2"
}
repo "$T/hal2" farmer
repo "$T/skills" 04
slot="$T/wt/skills/04"

mkdir -p "$FARMER_DIR/hal2" "$slot/plans/0001-x"
cat >"$FARMER_DIR/hal2/log.jsonl" <<'EOF'
{"at": "2026-10-05T22:04:13", "kind": "decision", "slot": "-", "what": "handoff skill: after clear-and-continue a servant asks the farmer 'did I forget a decision?'; built now by a servant in ~/a/skills (slot 04)", "note": "user: \"can we adapt the handoff so that it ensures, that after the clear and continue a servant always asks, if he forgot some decisions?\" then \"1\""}
{"at": "2026-10-05T21:41:34", "kind": "decision", "slot": "12", "what": "delete all old GitHub Actions workflow runs", "note": "user: \"it should delete all the old workflow runs\""}
EOF
cat >"$slot/plans/0001-x/plan.md" <<'EOF'
# Plan 0001: x

## Decisions

- 2026-10-05 (autogrill 1): the check runs as code.
EOF
echo 0001-x >"$slot/plans/CURRENT_PLAN"
printf '# Handoff\n\nUpdated 2026-10-05, branch `04`, written at `abc1234`.\nFarmer: farmer-a4 (hal2)\n' >"$slot/HANDOFF.md"

check() {  # the servant builds its message, the farmer answers it
  local msg
  msg="$(cd "$slot" && python3 "$skills/handoff/scripts/decisions.py" --json |
         python3 -c 'import json,sys; print(json.load(sys.stdin)["message"])')"
  echo "servant: $msg" >&2
  (cd "$T/wt/hal2/farmer" && python3 "$skills/farmer/scripts/farmer.py" decision-check --message "$msg")
}

first="$(check)"
echo "$first"
grep -q "decision check skills/04: 1 missing" <<<"$first"
grep -q '"can we adapt the handoff so that it ensures' <<<"$first"
! grep -q "workflow runs" <<<"$first"

# The servant writes the returned decision into its plan's Decisions, as handoff's Continue says.
line="$(grep '^- 2026' <<<"$first" | sed 's/^- \([0-9-]*\): \(.*\)\. The user.s words: \(.*\)$/- \1 (the user, via the farmer'"'"'s decision check): \2. User: \3/')"
printf '%s\n' "$line" >>"$slot/plans/0001-x/plan.md"

second="$(check)"
echo "$second"
[[ "$second" == "farmer: decision check skills/04: none missing" ]]
[[ "$(grep -c '"kind": "decision-check"' "$FARMER_DIR/hal2/log.jsonl")" == 2 ]]
echo "dry run ok"

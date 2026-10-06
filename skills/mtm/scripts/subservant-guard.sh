#!/usr/bin/env bash
# Refuse a landing in a parallel plan's subservant slot (skills plan 0013): the
# worktree at <dir> (default .) holds plans/LEAD (`<lead-slot> <plan> <step>`).
# Exit 1 naming the lead there, 0 silently elsewhere; 2 when git is missing.
set -euo pipefail
command -v git >/dev/null 2>&1 || { echo "subservant-guard.sh: git is missing: run install-prerequisites.sh" >&2; exit 2; }
dir="${1:-.}"
root=$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null || echo "$dir")
marker="$root/plans/LEAD"
[ -f "$marker" ] || exit 0
read -r lead plan step _ < "$marker" || true
echo "mtm: this slot is a subservant of slot ${lead:-?} (plan ${plan:-?} step ${step:-?}, plans/LEAD): it never lands." >&2
echo "Push your branch and report to the lead (plan.py report ${step:-<step>}); the lead in slot ${lead:-?} merges it." >&2
exit 1

#!/usr/bin/env bash
# Refuse a landing in a parallel plan's subservant slot (skills plan 0013): the
# worktree holds plans/LEAD (`<lead-slot> <plan> <step>`).
# Usage: subservant-guard.sh [<dir>|<slot>]   (default: the current directory)
#   <dir>  any directory inside the worktree to check;
#   <slot> a worktree's folder name (e.g. 31) when no such directory exists here:
#          resolved through `git worktree list --porcelain` of the current repo.
# Exit 1 naming the lead there, 0 silently elsewhere; 2 when git is missing;
# 3 when <slot> names no worktree of the current repo.
set -euo pipefail
command -v git >/dev/null 2>&1 || { echo "subservant-guard.sh: git is missing: run install-prerequisites.sh" >&2; exit 2; }
arg="${1:-.}"
if [ -d "$arg" ]; then
  dir="$arg"
else
  dir=$(git worktree list --porcelain 2>/dev/null \
    | awk -v name="$arg" 'sub(/^worktree /, "") { n = split($0, p, "/"); if (p[n] == name) { print; exit } }')
  [ -n "$dir" ] || { echo "subservant-guard.sh: no directory and no worktree of this repo named '$arg'" >&2; exit 3; }
fi
root=$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null || echo "$dir")
marker="$root/plans/LEAD"
[ -f "$marker" ] || exit 0
read -r lead plan step _ < "$marker" || true
echo "mtm: this slot is a subservant of slot ${lead:-?} (plan ${plan:-?} step ${step:-?}, plans/LEAD): it never lands." >&2
echo "Push your branch and report to the lead (plan.py report ${step:-<step>}); the lead in slot ${lead:-?} merges it." >&2
exit 1

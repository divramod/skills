#!/usr/bin/env bash
# Wait until no land.yml run is unfinished in the repository of <dir> (default .),
# so a landing through CI never reserves the queue or pushes a candidate while
# another landing still runs or ships (references/ci.md). A run counts until its
# status is `completed`: `queued` too (a ship job waiting for a runner is queued).
#   land-runs.sh [--once] [--interval <s>] [<dir>]
# Exit 0: none unfinished. --once: exit 6 and list them instead of waiting.
# Exit 2: gh is missing. Exit 1: gh failed, nothing is known: do not push.
set -euo pipefail
once=0
interval=60
dir=.
while [ $# -gt 0 ]; do
  case "$1" in
    --once) once=1 ;;
    --interval) shift; interval="$1" ;;
    *) dir="$1" ;;
  esac
  shift
done
if ! command -v gh >/dev/null 2>&1; then
  echo "land-runs.sh: gh is missing -> brew install gh (or: bash $(dirname "$0")/install-prerequisites.sh)" >&2
  exit 2
fi
cd "$dir"
unfinished() {
  gh run list --workflow land.yml --limit 10 --json databaseId,headBranch,status \
    --jq '.[] | select(.status != "completed") | "\(.databaseId) \(.headBranch) \(.status)"'
}
while :; do
  if ! runs=$(unfinished); then
    echo "land-runs.sh: gh run list failed (gh auth status?); cannot tell, do not push" >&2
    exit 1
  fi
  if [ -z "$runs" ]; then
    exit 0
  fi
  echo "land runs unfinished: $(echo "$runs" | paste -sd ',' - | sed 's/,/, /g')"
  if [ "$once" -eq 1 ]; then
    exit 6
  fi
  sleep "$interval"
done

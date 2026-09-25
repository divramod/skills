#!/usr/bin/env bash
# Check the external tools of every tell source (or one: --source <name>). Exit 1 if a required tool is missing.
# Each scripts/<source>/check-prerequisites.sh does the work; fix with install-prerequisites.sh [--source <name>].
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
only=""
[ "${1:-}" = "--source" ] && only="${2:-}"
status=0
for check in "$HERE"/*/check-prerequisites.sh; do
  src="$(basename "$(dirname "$check")")"
  [ -n "$only" ] && [ "$src" != "$only" ] && continue
  echo "== $src"
  "$check" || status=1
done
if [ -n "$only" ] && [ ! -x "$HERE/$only/check-prerequisites.sh" ]; then
  echo "unknown source: $only" >&2
  exit 1
fi
exit "$status"

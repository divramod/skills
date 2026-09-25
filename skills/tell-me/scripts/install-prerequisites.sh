#!/usr/bin/env bash
# Install the missing tools of every tell-me source (or one: --source <name>), then check them.
# Usage: install-prerequisites.sh [--source <name>] [--upgrade]   (--upgrade also upgrades yt-dlp)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
only="" upgrade=()
while [ $# -gt 0 ]; do
  case "$1" in
    --source) only="${2:-}"; shift 2 ;;
    --upgrade) upgrade=(--upgrade); shift ;;
    *) echo "usage: $0 [--source <name>] [--upgrade]" >&2; exit 2 ;;
  esac
done
if [ -n "$only" ] && [ ! -x "$HERE/$only/install-prerequisites.sh" ]; then
  echo "unknown source: $only" >&2
  exit 1
fi
for install in "$HERE"/*/install-prerequisites.sh; do
  src="$(basename "$(dirname "$install")")"
  [ -n "$only" ] && [ "$src" != "$only" ] && continue
  echo "== $src"
  "$install" ${upgrade[@]+"${upgrade[@]}"}
done

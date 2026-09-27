#!/usr/bin/env bash
# Check the external tools the tell topic scripts need. Exit 1 if a required tool is missing.
#   required: yt-dlp (the video search)
#   optional: gh (GitHub search: 30 requests/minute instead of 10), rg (local search where Spotlight is missing)
# The web and HN searches need no tools; Spotlight (mdfind) comes with macOS.
# Fix with: install-prerequisites.sh. --list prints the tools.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SOURCE=topic
REQUIRED=(yt-dlp)
OPTIONAL=("gh:GitHub search with a login (run gh auth login)" "rg:local document search where Spotlight (mdfind) is missing")
. "$HERE/../shared/prereqs.sh"

check_main "$@" || exit 1

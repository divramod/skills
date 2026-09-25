#!/usr/bin/env bash
# Check the external tools the tell github scripts need. Exit 1 if a required tool is missing.
#   required: none
#   optional: gh, npx
# Fix with: install-prerequisites.sh. --list prints the tools.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SOURCE=github
REQUIRED=()
OPTIONAL=("gh:5000 requests/hour, similar repos and discussions" "npx:--deep (repomix packs the whole repo)")
. "$HERE/../shared/prereqs.sh"

check_main "$@" || exit 1

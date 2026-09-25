#!/usr/bin/env bash
# Check the external tools the tell shared scripts need. Exit 1 if a required tool is missing.
#   required: python3
#   optional: gh
# Fix with: install-prerequisites.sh. --list prints the tools.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SOURCE=shared
REQUIRED=(python3)
OPTIONAL=("gh:GitHub release/commit dates beyond 60 requests/hour")
. "$HERE/../shared/prereqs.sh"

check_main "$@" || exit 1

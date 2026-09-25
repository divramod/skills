#!/usr/bin/env bash
# Check the external tools the tell web scripts need. Exit 1 if a required tool is missing.
#   required: uvx, npx
#   optional: none
# Fix with: install-prerequisites.sh. --list prints the tools.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SOURCE=web
REQUIRED=(uvx npx)
OPTIONAL=()
. "$HERE/../shared/prereqs.sh"

check_main "$@" || exit 1

#!/usr/bin/env bash
# Check the external tools the tell-me hn scripts need. Exit 1 if a required tool is missing.
#   required: uvx, npx (the linked article goes through the web source's extractor; text posts need none)
#   optional: none
# Fix with: install-prerequisites.sh. --list prints the tools.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SOURCE=hn
REQUIRED=(uvx npx)
OPTIONAL=()
. "$HERE/../shared/prereqs.sh"

check_main "$@" || exit 1

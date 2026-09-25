#!/usr/bin/env bash
# Check the external tools the tell-me reddit scripts need. Exit 1 if a required tool is missing.
#   required: uvx, npx (a link post's page goes through the web source's extractor; the Reddit APIs are plain HTTPS)
#   optional: none
# Fix with: install-prerequisites.sh. --list prints the tools.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SOURCE=reddit
REQUIRED=(uvx npx)
OPTIONAL=()
. "$HERE/../shared/prereqs.sh"

check_main "$@" || exit 1

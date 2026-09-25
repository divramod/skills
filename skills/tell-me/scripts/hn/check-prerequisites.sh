#!/usr/bin/env bash
# Check the external tools the tell-me hn scripts need. Exit 1 if a required tool is missing.
#   required: none
#   optional: none
# Fix with: install-prerequisites.sh. --list prints the tools.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SOURCE=hn
REQUIRED=()
OPTIONAL=()
. "$HERE/../shared/prereqs.sh"

check_main "$@" || exit 1

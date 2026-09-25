#!/usr/bin/env bash
# Check the external tools the tell-me file scripts need. Exit 1 if a required tool is missing.
#   required: uvx
#   optional: pdftotext, pandoc
# Fix with: install-prerequisites.sh. --list prints the tools.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SOURCE=file
REQUIRED=(uvx)
OPTIONAL=("pdftotext:PDF fallback when markitdown fails" "pandoc:fallback for docx/epub/odt")
. "$HERE/../shared/prereqs.sh"

check_main "$@" || exit 1

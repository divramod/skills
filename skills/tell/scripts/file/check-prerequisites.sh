#!/usr/bin/env bash
# Check the external tools the tell file scripts need. Exit 1 if a required tool is missing.
#   required: pdftotext (poppler: PDFs, keeps two-column reading order; pdfinfo comes with it), uvx (markitdown)
#   optional: pandoc (docx/epub/odt/html/rtf fallback), textutil (macOS only, built in: .doc and .rtf)
# Fix with: install-prerequisites.sh. --list prints the tools.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SOURCE=file
REQUIRED=(pdftotext uvx)
OPTIONAL=("pandoc:fallback for docx/epub/odt/html/rtf")
# textutil ships with macOS and exists nowhere else: only check (never install) it there.
[ "$(uname -s)" = Darwin ] && OPTIONAL+=("textutil:reads Word 97-2003 .doc and .rtf")
. "$HERE/../shared/prereqs.sh"

check_main "$@" || exit 1

#!/usr/bin/env bash
# Install the missing tools the tell file scripts need (Homebrew first, then apt-get), then check them:
# poppler (pdftotext, pdfinfo) and uv (uvx, runs markitdown) are required, pandoc is optional.
# Usage: install-prerequisites.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/../shared/prereqs.sh"
install_main "$HERE" "$@"

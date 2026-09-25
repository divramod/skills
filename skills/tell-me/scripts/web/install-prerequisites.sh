#!/usr/bin/env bash
# Install the missing tools the tell-me web scripts need (Homebrew first, then apt-get), then check them.
# Usage: install-prerequisites.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/../shared/prereqs.sh"
# fetch the pinned trafilatura and defuddle now: the first run would otherwise spend its extractor timeout on it
after_install() { have uvx && have npx && python3 "$HERE/extract.py" --warm; }
install_main "$HERE" "$@"

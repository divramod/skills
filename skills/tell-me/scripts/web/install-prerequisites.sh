#!/usr/bin/env bash
# Install the missing tools the tell-me web scripts need (Homebrew first, then apt-get), then check them.
# Usage: install-prerequisites.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/../shared/prereqs.sh"
# fetch the pinned trafilatura and defuddle now: the first run would otherwise spend its extractor timeout on it
after_install() {
  have uvx && have npx || return 0
  python3 "$HERE/extract.py" --warm || echo "warning: could not prefetch the extractors; the first run fetches them" >&2
}
install_main "$HERE" "$@"

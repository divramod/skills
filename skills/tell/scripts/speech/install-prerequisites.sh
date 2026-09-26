#!/usr/bin/env bash
# Install the missing tools the tell speech scripts need (Homebrew first, then apt-get), then check them.
# Usage: install-prerequisites.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/../shared/prereqs.sh"
# install the engine and download its model (~385 MB) now: the first "Read aloud" would otherwise wait for it
after_install() {
  have uv || return 0
  python3 "$HERE/speak.py" --warm || echo "warning: could not prefetch the voice model; the first recording fetches it" >&2
}
install_main "$HERE" "$@"

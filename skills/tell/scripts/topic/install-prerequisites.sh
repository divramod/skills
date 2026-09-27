#!/usr/bin/env bash
# Install the missing tools the tell topic scripts need (Homebrew first, then apt-get), then check them.
# Usage: install-prerequisites.sh [--upgrade]   (--upgrade also refreshes yt-dlp)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/../shared/prereqs.sh"
install_main "$HERE" "$@"

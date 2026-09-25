#!/usr/bin/env bash
# Install the missing tools the tell x scripts need (Homebrew first, then apt-get), then check them.
# Usage: install-prerequisites.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/../shared/prereqs.sh"
install_main "$HERE" "$@"

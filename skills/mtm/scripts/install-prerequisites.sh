#!/usr/bin/env bash
# Install the tools /mfm and /mtm need that are missing, then re-check.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for tool in git bash python3; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    if command -v brew >/dev/null 2>&1; then
      brew install "$tool"
    elif command -v apt-get >/dev/null 2>&1; then
      sudo apt-get install -y "$tool"
    else
      echo "install $tool manually: neither brew nor apt-get is available" >&2
    fi
  fi
done

install_hal2() {
  if ! command -v cargo >/dev/null 2>&1; then
    echo "install Rust first (https://rustup.rs), then rerun this script" >&2
  elif [ -d "$HOME/a/hal2/code/rust/apps/$1" ]; then
    cargo install --locked --path "$HOME/a/hal2/code/rust/apps/$1"
  else
    cargo install --locked --git https://github.com/divramod/hal2 "$1"
  fi
}

# hal2-cli-git with the declarative hooks (merge-to-main --json lists `tasks`).
if ! command -v hal2-cli-git >/dev/null 2>&1 || ! hal2-cli-git --help | grep -q 'merge-to-main .*--json' ||
  ! command -v hal2-cli-hooks >/dev/null 2>&1; then
  install_hal2 hal2-cli-git
fi
if ! command -v hal2-cli-hooks >/dev/null 2>&1 || ! hal2-cli-hooks --help | grep -q 'stamp'; then
  install_hal2 hal2-cli-hooks
fi

bash "$here/check-prerequisites.sh"

#!/usr/bin/env bash
# Install the external tools dm-summarize-video needs (only the missing ones).
#   macOS / Linux with Homebrew: brew install yt-dlp ffmpeg uv python
#   Debian/Ubuntu without brew:  apt-get install ffmpeg python3; uv via astral.sh; yt-dlp via `uv tool`
# Usage: install-prerequisites.sh [--upgrade]   (--upgrade also upgrades yt-dlp, which ages fast)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
UPGRADE=0
[ "${1:-}" = "--upgrade" ] && UPGRADE=1
have() { command -v "$1" >/dev/null 2>&1; }

if have brew; then
  pkgs=()
  have yt-dlp || pkgs+=(yt-dlp)
  { have ffmpeg && have ffprobe; } || pkgs+=(ffmpeg)
  have uvx || pkgs+=(uv)
  have python3 || pkgs+=(python)
  if [ "${#pkgs[@]}" -gt 0 ]; then
    echo "brew install ${pkgs[*]}"
    brew install "${pkgs[@]}"
  fi
  if [ "$UPGRADE" -eq 1 ]; then
    brew upgrade yt-dlp || true
  fi
elif have apt-get; then
  SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
  pkgs=()
  { have ffmpeg && have ffprobe; } || pkgs+=(ffmpeg)
  have python3 || pkgs+=(python3)
  have curl || pkgs+=(curl)
  if [ "${#pkgs[@]}" -gt 0 ]; then
    $SUDO apt-get update && $SUDO apt-get install -y "${pkgs[@]}"
  fi
  if ! have uvx; then
    echo "installing uv (https://astral.sh/uv)"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
  fi
  if ! have yt-dlp; then
    uv tool install "yt-dlp[default]"
  elif [ "$UPGRADE" -eq 1 ]; then
    uv tool upgrade yt-dlp || echo "upgrade yt-dlp manually (it was not installed via uv)" >&2
  fi
else
  echo "error: neither Homebrew nor apt-get found. Install yt-dlp, ffmpeg, python3 and uv manually:" >&2
  echo "  https://github.com/yt-dlp/yt-dlp#installation  https://ffmpeg.org/download.html  https://docs.astral.sh/uv/" >&2
  exit 1
fi

"$HERE/check-prerequisites.sh"

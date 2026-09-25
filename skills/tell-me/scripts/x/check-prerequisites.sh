#!/usr/bin/env bash
# Check the external tools the tell-me x scripts need. Exit 1 if a required tool is missing.
#   required: none
#   optional: yt-dlp, ffmpeg
# Fix with: install-prerequisites.sh. --list prints the tools.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SOURCE=x
REQUIRED=()
OPTIONAL=("yt-dlp:transcripts of posts with a video" "ffmpeg:downloads of posts with a video")
. "$HERE/../shared/prereqs.sh"

check_main "$@" || exit 1

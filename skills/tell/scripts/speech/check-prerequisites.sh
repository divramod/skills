#!/usr/bin/env bash
# Check the external tools the tell speech scripts (read a summary aloud) need. Exit 1 if a required tool is missing.
#   required: uv (runs the Supertonic-3 text-to-speech engine in its own environment)
#   optional: ffmpeg
# Fix with: install-prerequisites.sh. --list prints the tools.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SOURCE=speech
REQUIRED=(uv)
OPTIONAL=("ffmpeg:compresses the recording to .m4a, else it stays a .wav")
. "$HERE/../shared/prereqs.sh"

check_main "$@" || exit 1

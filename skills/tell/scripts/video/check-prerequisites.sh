#!/usr/bin/env bash
# Check the external tools the tell video scripts need. Exit 1 if a required tool is missing.
#   required: yt-dlp, ffmpeg, ffprobe
#   optional: uvx
# Fix with: install-prerequisites.sh (add --upgrade to refresh yt-dlp). --list prints the tools.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SOURCE=video
REQUIRED=(yt-dlp ffmpeg ffprobe)
OPTIONAL=("uvx:the Whisper fallback when a video has no captions")
. "$HERE/../shared/prereqs.sh"

check_main "$@" || exit 1

# YouTube breaks old yt-dlp versions quickly: warn when it is older than 60 days.
if [ "${1:-}" != "--list" ] && have yt-dlp && have python3; then
  ver="$(yt-dlp --version 2>/dev/null)"
  age="$(python3 -c 'import sys,datetime as d
try:
    y,m,day=(int(x) for x in sys.argv[1].split(".")[:3]); print((d.date.today()-d.date(y,m,day)).days)
except Exception: print(-1)' "$ver")"
  if [ "$age" -gt 60 ]; then
    echo "warning  yt-dlp $ver is $age days old; YouTube downloads may fail -> $HERE/install-prerequisites.sh --upgrade" >&2
  fi
fi

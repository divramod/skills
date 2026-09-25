#!/usr/bin/env bash
# Check the external tools dm-summarize-video needs. Exit 1 if a required tool is missing.
#   required: yt-dlp, ffmpeg, ffprobe, python3
#   optional: uvx (Whisper fallback when a video has no captions)
# Also warns when yt-dlp is older than 60 days: YouTube breaks old versions quickly.
# Fix everything with: install-prerequisites.sh  (add --upgrade to refresh yt-dlp)
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REQUIRED=(yt-dlp ffmpeg ffprobe python3)
OPTIONAL=(uvx)
missing=0

hint() {
  case "$1" in
    yt-dlp) echo "brew install yt-dlp" ;;
    ffmpeg|ffprobe) echo "brew install ffmpeg" ;;
    python3) echo "brew install python" ;;
    uvx) echo "brew install uv" ;;
  esac
}

for t in "${REQUIRED[@]}"; do
  if command -v "$t" >/dev/null 2>&1; then
    echo "ok       $t"
  else
    echo "MISSING  $t (required) -> $(hint "$t")" >&2
    missing=1
  fi
done
for t in "${OPTIONAL[@]}"; do
  if command -v "$t" >/dev/null 2>&1; then
    echo "ok       $t"
  else
    echo "missing  $t (optional, needed for the Whisper fallback) -> $(hint "$t")" >&2
  fi
done

if command -v yt-dlp >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1; then
  ver="$(yt-dlp --version 2>/dev/null)"
  age="$(python3 -c 'import sys,datetime as d
try:
    y,m,day=(int(x) for x in sys.argv[1].split(".")[:3]); print((d.date.today()-d.date(y,m,day)).days)
except Exception: print(-1)' "$ver")"
  if [ "$age" -gt 60 ]; then
    echo "warning  yt-dlp $ver is $age days old; YouTube downloads may fail -> $HERE/install-prerequisites.sh --upgrade" >&2
  fi
fi

if [ "$missing" -ne 0 ]; then
  echo "Install missing tools with: $HERE/install-prerequisites.sh" >&2
  exit 1
fi

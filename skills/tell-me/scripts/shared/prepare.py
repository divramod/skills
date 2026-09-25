#!/usr/bin/env python3
"""Prepare any input for summarizing: route it to its source, run scripts/<source>/prepare.py.

route.py picks the source (video, web, github, x, hn, file); the source script fetches the content
into its library folder (content file with anchor links + metadata.json) and prints the envelope.
This script checks the envelope and prints it unchanged, so the agent reads `subskill` and
`template` next. Every flag after the input goes to the source script (e.g. --skip-download,
--visual, --lang for video). Exit codes pass through: 1 expected error, 2 missing tool (the
message names the source's install-prerequisites.sh).

Usage: prepare.py "<url-or-path>" [source flags]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from _common import ENVELOPE_KEYS, SkillError, is_legacy, log, read_json, run_main, source_root
from route import route

SOURCES_DIR = Path(__file__).resolve().parent.parent  # scripts/
LIST_KINDS = ("playlist", "channel")


def dispatch(text: str, flags: list[str], sources_dir: Path = SOURCES_DIR) -> tuple[int, dict | None]:
    """(exit code, envelope). The source script's progress goes straight to stderr."""
    r = route(text)
    script = sources_dir / r["source"] / "prepare.py"
    if not script.is_file():
        video = sources_dir / "video" / "prepare.py"
        if not r.get("url") or not video.is_file():
            raise SkillError(f"source '{r['source']}' not supported yet ({text})")
        # yt-dlp reads many pages that later get their own source (X posts with a video, pages with an embed)
        log(f"source '{r['source']}' not supported yet: trying the video source (yt-dlp)")
        r, script = r | {"source": "video"}, video
    log(f"source: {r['source']} ({r['kind']}) -> {script.relative_to(sources_dir)}")
    p = subprocess.run([sys.executable, str(script), r.get("url") or r["path"], *flags],
                       stdout=subprocess.PIPE, text=True)
    if p.returncode != 0:
        return p.returncode, None
    try:
        env = json.loads(p.stdout)
    except json.JSONDecodeError as e:
        raise SkillError(f"{script} printed no JSON envelope: {e}")
    # A playlist/channel lists its items (each prepared on its own) instead of having content.
    required = ("source", "kind", "dir", "title", "subskill") if env.get("kind") in LIST_KINDS else ENVELOPE_KEYS
    missing = [k for k in required if k not in env]
    if missing:
        raise SkillError(f"{script} envelope is missing {', '.join(missing)}")
    return 0, env


def warn_legacy() -> None:
    """Point at the migration when the video library still has folders from before the multi-source layout."""
    videos = source_root("video")
    n = sum(1 for m in videos.rglob("metadata.json") if is_legacy(read_json(m))) if videos.is_dir() else 0
    if n:
        log(f"{n} video folder(s) use the old layout: run {SOURCES_DIR / 'video' / 'migrate_library.py'} --apply "
            "(tell the user; it renames transcript.md to content.md and re-renders the pages)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="URL or local file path")
    raw = sys.argv[1:] if argv is None else argv
    if raw and raw[0].startswith("-") and raw[0] not in ("-h", "--help"):
        ap.error(f"put the URL or path first, then the source flags (got {raw[0]!r} first)")
    args, flags = ap.parse_known_args(raw)
    warn_legacy()
    code, env = dispatch(args.input, flags)
    if env is not None:
        print(json.dumps(env, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    run_main(main)

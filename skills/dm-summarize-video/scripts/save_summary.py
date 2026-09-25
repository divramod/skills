#!/usr/bin/env python3
"""Save an agent-written summary body as summary.md (or digest.md) with frontmatter + header.

The agent writes only the body (TL;DR, key points, ...). This script adds YAML frontmatter
and the title/metadata header from the folder's metadata.json, so every note in the library
looks the same.

Usage: save_summary.py <folder> [--mode summary] [--summary-lang en] [--body-file F] < body.md
<folder> is a video folder from prepare_video.py or a digest folder from list_videos.py.
Prints the written file path.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

from _common import SkillError, fmt_ts, read_json, run_main

MODES = ("tldr", "summary", "chapters", "detailed", "wisdom", "qa", "digest")


def fmt_date(upload_date: str | None) -> str | None:
    if upload_date and re.fullmatch(r"\d{8}", upload_date):
        return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
    return upload_date


def yaml_scalar(value) -> str:
    """JSON scalars are valid YAML and always safely quoted."""
    return json.dumps(value, ensure_ascii=False)


def strip_leading_h1(body: str) -> str:
    return re.sub(r"\A\s*# [^\n]*\n+", "", body)


def render(meta: dict, body: str, mode: str, lang: str | None, today: str) -> str:
    digest = meta.get("kind") == "digest"
    front = {
        "title": meta.get("title"),
        "channel": meta.get("channel") or meta.get("uploader"),
        "url": meta.get("webpage_url"),
        "published": fmt_date(meta.get("upload_date")),
        "duration": fmt_ts(meta["duration"]) if meta.get("duration") else None,
        "platform": meta.get("platform"),
        "video_id": meta.get("id") if not digest else None,
        "videos": len(meta.get("videos") or []) if digest else None,
        "mode": mode,
        "lang": lang,
        "transcript_source": meta.get("transcript_source"),
        "video_file": meta.get("video_file"),
        "created": today,
    }
    lines = ["---"] + [f"{k}: {yaml_scalar(v)}" for k, v in front.items() if v not in (None, "")] + ["---", ""]
    info = " · ".join(str(x) for x in (front["channel"], front["duration"], front["published"], front["url"]) if x)
    lines += [f"# {meta.get('title') or 'Untitled'}", "", info, "", strip_leading_h1(body).strip(), ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path)
    ap.add_argument("--mode", choices=MODES, default=None, help="default: summary (digest for digest folders)")
    ap.add_argument("--summary-lang", help="language the summary is written in (e.g. en, de)")
    ap.add_argument("--body-file", type=Path, help="read the body from a file instead of stdin")
    args = ap.parse_args(argv)

    meta = read_json(args.folder / "metadata.json")
    if not meta:
        raise SkillError(f"{args.folder}/metadata.json missing: run prepare_video.py or list_videos.py first")
    body = args.body_file.read_text(encoding="utf-8") if args.body_file else sys.stdin.read()
    if not body.strip():
        raise SkillError("empty summary body")
    digest = meta.get("kind") == "digest"
    mode = args.mode or ("digest" if digest else "summary")
    out = args.folder / ("digest.md" if digest else "summary.md")
    out.write_text(render(meta, body, mode, args.summary_lang, date.today().isoformat()), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    run_main(main)

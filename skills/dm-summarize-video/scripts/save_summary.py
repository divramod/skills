#!/usr/bin/env python3
"""Save an agent-written summary body as summary.md + summary.html (or digest.md + digest.html).

The agent writes only the body (TL;DR, key points, ...). This script adds YAML frontmatter
and the title/metadata header from the folder's metadata.json, so every note in the library
looks the same, records which agentic CLI wrote it (auto-detected, or --agent/--model), and
renders the HTML page (render_html.py).

Usage: save_summary.py <folder> [--mode summary] [--summary-lang en] [--agent NAME] [--model M]
                       [--body-file F] [--open] < body.md
<folder> is a video folder from prepare_video.py or a digest folder from list_videos.py.
Prints the written file paths (markdown, then html).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

from _common import SkillError, detect_agent, fmt_ts, read_json, run_main, update_json

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


def render(meta: dict, body: str, mode: str, lang: str | None, today: str,
           agent: str | None = None, model: str | None = None) -> str:
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
        "agent": agent,
        "model": model,
        "created": today,
    }
    lines = ["---"] + [f"{k}: {yaml_scalar(v)}" for k, v in front.items() if v not in (None, "")] + ["---", ""]
    info = " · ".join(str(x) for x in (front["channel"], front["duration"], front["published"], front["url"]) if x)
    lines += [f"# {meta.get('title') or 'Untitled'}", "", info, "", strip_leading_h1(body).strip(), ""]
    return "\n".join(lines)


def set_frontmatter_field(text: str, key: str, value, before: str = "agent") -> str:
    """Set `key` in a note's frontmatter; a new key goes before `before` (or at the end)."""
    end = text.find("\n---\n", 4)
    if not text.startswith("---\n") or end < 0:
        return text
    lines = text[4:end].split("\n")
    row = f"{key}: {yaml_scalar(value)}"
    for i, line in enumerate(lines):
        if line.startswith(f"{key}:"):
            lines[i] = row
            break
    else:
        at = next((i for i, line in enumerate(lines) if line.split(":")[0] in (before, "created")), len(lines))
        lines.insert(at, row)
    return "---\n" + "\n".join(lines) + text[end:]


def remove_frontmatter_field(text: str, key: str) -> str:
    end = text.find("\n---\n", 4)
    if not text.startswith("---\n") or end < 0:
        return text
    lines = [line for line in text[4:end].split("\n") if not line.startswith(f"{key}:")]
    return "---\n" + "\n".join(lines) + text[end:]


def refresh(folder: Path) -> list[Path]:
    """Re-sync an already-saved note with metadata.json (e.g. after the background video
    download finished) and re-render its HTML. Returns the files written; [] when no note yet."""
    from render_html import write as write_html
    meta = read_json(folder / "metadata.json")
    note = folder / ("digest.md" if meta.get("kind") == "digest" else "summary.md")
    if not note.exists():
        return []
    text = note.read_text(encoding="utf-8")
    if meta.get("video_file"):
        text = set_frontmatter_field(text, "video_file", meta["video_file"])
    else:  # the video was deleted
        text = remove_frontmatter_field(text, "video_file")
    note.write_text(text, encoding="utf-8")
    return [note, write_html(folder)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path)
    ap.add_argument("--mode", choices=MODES, default=None, help="default: summary (digest for digest folders)")
    ap.add_argument("--summary-lang", help="language the summary is written in (e.g. en, de)")
    ap.add_argument("--agent", help="agentic CLI that wrote the summary (default: auto-detected, e.g. claude-code, codex, grok)")
    ap.add_argument("--model", help="model that wrote the summary (e.g. claude-opus-5-5)")
    ap.add_argument("--body-file", type=Path, help="read the body from a file instead of stdin")
    ap.add_argument("--open", action="store_true", help="open the HTML page in the default browser")
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
    agent = args.agent or detect_agent()
    today = date.today().isoformat()
    out.write_text(render(meta, body, mode, args.summary_lang, today, agent, args.model), encoding="utf-8")
    update_json(args.folder / "metadata.json", {
        "summary": {k: v for k, v in {"mode": mode, "lang": args.summary_lang, "agent": agent,
                                      "model": args.model, "created": today,
                                      "created_at": datetime.now().isoformat(timespec="seconds")}.items() if v}})
    from render_html import write as write_html
    page = write_html(args.folder)
    print(out)
    print(page)
    if args.open:
        from render_html import open_page
        print(open_page(page))
    return 0


if __name__ == "__main__":
    run_main(main)

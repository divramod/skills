#!/usr/bin/env python3
"""Find videos similar to a summarized one via yt-dlp's YouTube search (real links, no guessing).

The agent picks the queries (the topic, the key concepts, "<channel> <topic>"); this script runs
them, merges the results, drops duplicates and the video itself, and marks videos that already
have a summary in the library. Prints JSON: {"videos": [{id, title, url, channel, duration,
views, published, query, summary?}]}, where `published` is the upload date (search results don't
carry it, so each video is looked up with yt-dlp, in parallel) and `summary` is a path relative to
<folder> to that video's page.

Usage: related.py <folder> --query "fine-tuning llms with lora" [--query ...] [--per-query 8]
Requires: yt-dlp.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import sys

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

from link_dates import youtube_dates
from _common import (BOT_HINT, SkillError, fmt_ts, is_bot_error, library_root, log, read_json, require,
                     run_main, ytdlp_base)


def search(query: str, limit: int, cookies: str | None = None) -> list[dict]:
    p = subprocess.run(ytdlp_base(cookies) + ["--flat-playlist", "-J", f"ytsearch{limit}:{query}"],
                       capture_output=True, text=True)
    if p.returncode != 0:
        err = p.stderr.strip()
        log(f"search failed for {query!r}: {err[-200:]}" + (f"\n{BOT_HINT}" if is_bot_error(err) else ""))
        return []
    return json.loads(p.stdout).get("entries") or []


def summarized_ids(root: Path) -> dict[str, Path]:
    """Video id -> page path for every summarized video in the library."""
    out = {}
    for meta_path in root.glob("*/*/*/metadata.json"):
        meta = read_json(meta_path)
        page = meta_path.parent / "summary.html"
        if meta.get("id") and page.exists():
            out[meta["id"]] = page
    return out


def merge(results: list[tuple[str, list[dict]]], exclude_id: str | None, known: dict[str, Path],
          folder: Path) -> list[dict]:
    """Flatten per-query results in query order, dropping duplicates, the video itself, shorts and live streams."""
    seen = {exclude_id}
    videos = []
    for query, entries in results:
        for e in entries:
            vid = e.get("id")
            if not vid or vid in seen or e.get("live_status") in ("is_live", "is_upcoming"):
                continue
            if "/shorts/" in (e.get("url") or ""):
                continue
            seen.add(vid)
            v = {
                "id": vid,
                "title": e.get("title"),
                "url": f"https://www.youtube.com/watch?v={vid}",
                "channel": e.get("channel") or e.get("uploader"),
                "duration": fmt_ts(e["duration"]) if e.get("duration") else None,
                "views": e.get("view_count"),
                "query": query,
            }
            if vid in known:
                v["summary"] = os.path.relpath(known[vid], folder).replace(os.sep, "/")
            videos.append({k: val for k, val in v.items() if val is not None})
    return videos


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path)
    ap.add_argument("--query", action="append", required=True, help="search query; repeat for several")
    ap.add_argument("--per-query", type=int, default=8)
    ap.add_argument("--cookies-from-browser", default=os.environ.get("DM_SUMMARIZE_VIDEO_BROWSER"))
    args = ap.parse_args(argv)
    require("yt-dlp")
    meta = read_json(args.folder / "metadata.json")
    if not meta:
        raise SkillError(f"{args.folder}/metadata.json missing: run prepare_video.py first")
    with ThreadPoolExecutor(max_workers=4) as pool:
        found = list(pool.map(lambda q: (q, search(q, args.per_query, args.cookies_from_browser)), args.query))
    videos = merge(found, meta.get("id"), summarized_ids(library_root()), args.folder.resolve())
    dates = youtube_dates([v["id"] for v in videos])
    for v in videos:
        if dates.get(v["id"]):
            v["published"] = dates[v["id"]]
    log(f"{len(videos)} candidate videos from {len(args.query)} queries")
    print(json.dumps({"videos": videos}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    run_main(main)

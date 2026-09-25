#!/usr/bin/env python3
"""Expand a playlist or channel URL into its videos and create a digest folder.

Channel URLs (youtube.com/@handle, /channel/..., /c/..., /user/...) list the latest
--limit uploads; playlists list all videos (or the first --limit). Creates
<root>/<platform>/<user>/_digests/<slug>/metadata.json (kind: digest) so the agent can
save digest.md there with save_summary.py. Prints one JSON object on stdout:
{kind, title, channel, digest_dir, videos: [{id, title, url, duration, summary_exists}]}.

Usage: list_videos.py <playlist-or-channel-url> [--limit 10]
Requires: yt-dlp.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import date

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

from _common import (BOT_HINT, SkillError, SKILL_DIR, digest_dir, find_existing, is_bot_error, log, platform_of,
                     require, run_main, slugify, source_root, user_of)

_CHANNEL_RE = re.compile(r"youtube\.com/(@[^/?#]+|channel/[^/?#]+|c/[^/?#]+|user/[^/?#]+)/?(\?.*)?$")


def normalize_url(url: str) -> tuple[str, str]:
    """(url, kind): bare YouTube channel URLs point at their /videos tab."""
    m = _CHANNEL_RE.search(url)
    if m:
        return url.split("?")[0].rstrip("/") + "/videos", "channel"
    if "/videos" in url or "/streams" in url or "/shorts" in url:
        return url, "channel"
    return url, "playlist"


def parse_listing(data: dict, kind: str, limit: int | None, today: str) -> dict:
    """Turn `yt-dlp --flat-playlist -J` output into the digest description."""
    entries = [e for e in (data.get("entries") or []) if e]
    if entries and all(e.get("_type") == "playlist" for e in entries):
        raise SkillError("URL lists sub-playlists (channel tabs); pass the /videos tab or a playlist URL")
    videos = []
    for e in entries[: limit or None]:
        vid = e.get("id")
        url = e.get("url") or e.get("webpage_url")
        if platform_of(data) == "youtube" and vid:
            url = f"https://www.youtube.com/watch?v={vid}"
        if not url:
            continue
        videos.append({"id": vid, "title": e.get("title"), "url": url, "duration": e.get("duration")})
    channel = data.get("channel") or data.get("uploader") or data.get("title")
    title = data.get("title") or channel or "playlist"
    slug = slugify(title)
    if kind == "channel":
        slug = f"{slugify(channel)}-latest-{len(videos)}-{today}"
    return {"kind": kind, "title": title, "channel": channel, "slug": slug, "videos": videos}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--limit", type=int, default=None, help="max videos (channels default to 10)")
    ap.add_argument("--cookies-from-browser", default=os.environ.get("DM_SUMMARIZE_VIDEO_BROWSER"))
    args = ap.parse_args(argv)

    require("yt-dlp")
    url, kind = normalize_url(args.url)
    limit = args.limit or (10 if kind == "channel" else None)
    cmd = ["yt-dlp", "--flat-playlist", "--dump-single-json", "--no-warnings"]
    if limit:
        cmd += ["--playlist-end", str(limit)]
    if args.cookies_from_browser:
        cmd += ["--cookies-from-browser", args.cookies_from_browser]
    log(f"listing {kind}: {url}")
    p = subprocess.run(cmd + [url], capture_output=True, text=True)
    if p.returncode != 0:
        err = p.stderr.strip()
        raise SkillError(f"yt-dlp could not list videos:\n{err}" + (f"\n{BOT_HINT}" if is_bot_error(err) else ""))
    data = json.loads(p.stdout)
    listing = parse_listing(data, kind, limit, date.today().isoformat())

    for v in listing["videos"]:
        v["summary_exists"] = bool((d := find_existing({**data, "id": v["id"]})) and (d / "summary.md").exists())
    folder = digest_dir(listing["videos"], date.today().isoformat(),
                        folder=source_root("video") / platform_of(data) / user_of(data) / "_digests" / listing["slug"],
                        title=listing["title"], source_kind=kind, channel=listing["channel"], webpage_url=args.url,
                        platform=platform_of(data))
    print(json.dumps({"source": "video", "dir": str(folder), "digest_dir": str(folder), **listing,
                      "subskill": str(SKILL_DIR / "subskills" / "video" / "SUBSKILL.md"),
                      "template": str(SKILL_DIR / "templates" / "shared" / "digest.md")}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    run_main(main)

#!/usr/bin/env python3
"""Download a video into its library folder as video.<ext>; runs in the background by default.

prepare_video.py starts this detached (unless --skip-download), so the transcript and summary don't
wait for a multi-hundred-MB download. While it runs, `.video-download.json` in the folder
holds {status: running, pid, quality}. It becomes {status: failed, error} on failure and is removed on success.
When it finishes it writes title, artist, date, URL and chapters into the file (ffmpeg remux, no
re-encoding; players like VLC show the title instead of "video.mkv"), merges video_file/video_quality
into metadata.json and, if the summary was already saved, refreshes summary.md + summary.html.

Usage: download_video.py <folder> <url> [--quality best|1080p] [--have-quality Q] [--cookies-from-browser B]
       download_video.py <folder> --tag      (write the metadata into an existing video.<ext>)
       download_video.py <folder> --delete   (delete video.<ext> and refresh the note)
Requires: yt-dlp, ffmpeg.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
import sys
from datetime import datetime
from pathlib import Path

from _common import (BOT_HINT, SkillError, find_file, is_bot_error, log, read_json, require, run_main,
                     update_json, write_json, ytdlp_base)

# best: best video + best audio, no height cap. 1080p: enough for keyframes.
DOWNLOAD_FORMATS = {
    "best": "bv*+ba/b",
    "1080p": "bv*[height<=1080]+ba/b[height<=1080]/b",
}
STATUS_FILE = ".video-download.json"


def download_action(has_file: bool, wanted: str, have: str | None) -> str:
    """'download', 'reuse' or 'replace': a `best` request upgrades any non-best file."""
    if not has_file:
        return "download"
    if wanted == "best" and have != "best":
        return "replace"
    return "reuse"


def pid_alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError, TypeError):
        return False
    return True


def download_status(folder: Path) -> dict | None:
    """{status: running|failed, ...} for a background download, or None when there is none."""
    status = read_json(folder / STATUS_FILE)
    if not status:
        return None
    if status.get("status") == "running" and not pid_alive(status.get("pid")):
        return {**status, "status": "failed", "error": "download process exited unexpectedly"}
    return status


def is_running(folder: Path) -> bool:
    return (download_status(folder) or {}).get("status") == "running"


_PROGRESS_RE = re.compile(r"^\[download\]\s+([\d.]+)%")


def parse_progress(line: str) -> float | None:
    """Percent from a yt-dlp `[download]  42.0% of ...` line, else None."""
    m = _PROGRESS_RE.match(line.strip())
    return float(m.group(1)) if m else None


def download(folder: Path, url: str, quality: str, have_quality: str | None, cookies: str | None,
             on_progress=None) -> Path:
    """Download video.<ext>; an existing lower-quality file is replaced when `best` is wanted.

    `on_progress(stream, percent)` is called for each yt-dlp progress line; stream counts the
    separately downloaded video and audio streams (1, 2, ...).
    """
    existing = find_file(folder, "video")
    action = download_action(existing is not None, quality, have_quality)
    if action == "reuse":
        log(f"video already downloaded: {existing.name} ({have_quality or 'unknown quality'})")
        return existing
    if action == "replace":
        log(f"replacing {existing.name} ({have_quality or 'unknown quality'}) with the best available quality")
        existing.unlink()
    log(f"downloading video ({'highest available quality' if quality == 'best' else '<=1080p'})")
    proc = subprocess.Popen(ytdlp_base(cookies) + [
        "--newline", "-f", DOWNLOAD_FORMATS[quality], "--merge-output-format", "mp4/mkv",
        "-o", str(folder / "video.%(ext)s"), url], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    tail: list[str] = []
    stream, last = 1, 0.0
    for line in proc.stdout:
        tail = (tail + [line.rstrip()])[-20:]
        pct = parse_progress(line)
        if pct is None:
            continue
        if pct < last:  # yt-dlp moved on to the next stream (video, then audio)
            stream += 1
        last = pct
        if on_progress:
            on_progress(stream, pct)
    proc.wait()
    video = find_file(folder, "video")
    if not video:
        err = "\n".join(tail)
        raise SkillError(f"video download failed:\n{err[-800:]}" + (f"\n{BOT_HINT}" if is_bot_error(err) else ""))
    return video


def _ffescape(value) -> str:
    """Escape a value for ffmpeg's FFMETADATA1 format."""
    return re.sub(r"([=;#\\\n])", r"\\\1", str(value))


def ffmetadata(meta: dict) -> str:
    """FFMETADATA1 text: title/artist/date/comment tags plus chapters from metadata.json."""
    tags = {
        "title": meta.get("title"),
        "artist": meta.get("channel") or meta.get("uploader"),
        "date": (meta.get("upload_date") or "")[:4] or None,
        "comment": meta.get("webpage_url"),
        "description": (meta.get("description") or "")[:1000] or None,
    }
    lines = [";FFMETADATA1"] + [f"{k}={_ffescape(v)}" for k, v in tags.items() if v]
    chapters = sorted(meta.get("chapters") or [], key=lambda c: c.get("start_time", 0))
    duration = meta.get("duration")
    for i, ch in enumerate(chapters):
        start = ch.get("start_time", 0)
        end = ch.get("end_time") or (chapters[i + 1].get("start_time") if i + 1 < len(chapters) else duration)
        if end is None or end <= start:
            continue
        lines += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(start * 1000)}", f"END={int(end * 1000)}",
                  f"title={_ffescape(ch.get('title') or f'Chapter {i + 1}')}"]
    return "\n".join(lines) + "\n"


def tag_video(folder: Path, video: Path) -> bool:
    """Write metadata.json's title/artist/date/url/chapters into the video (stream copy). False on failure."""
    require("ffmpeg")
    meta = read_json(folder / "metadata.json")
    if not meta.get("title"):
        return False
    meta_file = folder / ".ffmetadata.txt"
    tmp = video.with_name(f"video.tagging{video.suffix}")
    meta_file.write_text(ffmetadata(meta), encoding="utf-8")
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-y", "-i", str(video), "-f", "ffmetadata",
                        "-i", str(meta_file), "-map", "0", "-map_metadata", "1", "-map_chapters", "1",
                        "-c", "copy", str(tmp)], capture_output=True, text=True)
    meta_file.unlink(missing_ok=True)
    if p.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        log(f"could not tag {video.name} (the video is fine, just untagged): {p.stderr.strip()[-300:]}")
        return False
    os.replace(tmp, video)
    return True


def delete_video(folder: Path) -> Path | None:
    """Delete video.<ext> and drop it from metadata.json; returns the deleted file or None."""
    if is_running(folder):
        raise SkillError("a video download is still running for this folder")
    video = find_file(folder, "video")
    if video:
        video.unlink()
    meta = read_json(folder / "metadata.json")
    if meta and ("video_file" in meta or "video_quality" in meta):
        meta.pop("video_file", None)
        meta.pop("video_quality", None)
        write_json(folder / "metadata.json", meta)
    (folder / STATUS_FILE).unlink(missing_ok=True)
    return video


def record(folder: Path, video: Path, quality: str) -> None:
    """Merge the finished video into metadata.json (merge: prepare_video.py may write concurrently)."""
    update_json(folder / "metadata.json", {"video_file": video.name, "video_quality": quality})


def start_background(folder: Path, url: str, quality: str, have_quality: str | None, cookies: str | None) -> dict:
    """Start this script detached from the caller; returns the status record."""
    status = download_status(folder)
    if status and status.get("status") == "running":
        log(f"video download already running (pid {status['pid']})")
        return status
    cmd = [sys.executable, str(Path(__file__).resolve()), str(folder), url, "--quality", quality]
    if have_quality:
        cmd += ["--have-quality", have_quality]
    if cookies:
        cmd += ["--cookies-from-browser", cookies]
    log_path = folder / ".video-download.log"
    with open(log_path, "w") as logf:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=logf, stderr=logf, start_new_session=True)
    status = {"status": "running", "pid": proc.pid, "quality": quality, "log": str(log_path),
              "started": datetime.now().isoformat(timespec="seconds")}
    write_json(folder / STATUS_FILE, status)
    log(f"video download started in the background (pid {proc.pid}, log {log_path})")
    return status


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path)
    ap.add_argument("url", nargs="?")
    ap.add_argument("--tag", action="store_true", help="only write the metadata into the existing video.<ext>")
    ap.add_argument("--delete", action="store_true", help="delete video.<ext> and refresh summary.md/.html")
    ap.add_argument("--quality", choices=list(DOWNLOAD_FORMATS), default="best")
    ap.add_argument("--have-quality", help="quality of an existing video.<ext> (from metadata.json)")
    ap.add_argument("--cookies-from-browser")
    args = ap.parse_args(argv)

    from save_summary import refresh
    if args.delete:
        video = delete_video(args.folder)
        refresh(args.folder)
        print(json.dumps({"deleted": str(video) if video else None}))
        return 0
    if args.tag:
        video = find_file(args.folder, "video")
        if not video:
            raise SkillError(f"no video.<ext> in {args.folder}")
        print(json.dumps({"video_file": str(video), "tagged": tag_video(args.folder, video)}))
        return 0
    if not args.url:
        ap.error("url is required unless --tag or --delete is given")
    require("yt-dlp", "ffmpeg")
    status_path = args.folder / STATUS_FILE
    status = read_json(status_path)
    if not status or status.get("pid") != os.getpid():  # started by hand, not via start_background
        write_json(status_path, {"status": "running", "pid": os.getpid(), "quality": args.quality})
    status = read_json(status_path)
    last_write = 0.0

    def progress(stream: int, pct: float) -> None:
        nonlocal last_write
        if time.monotonic() - last_write >= 1 or pct >= 100:
            write_json(status_path, status | {"progress": pct, "stream": stream})
            last_write = time.monotonic()

    try:
        video = download(args.folder, args.url, args.quality, args.have_quality, args.cookies_from_browser, progress)
    except SkillError as e:
        write_json(status_path, {"status": "failed", "quality": args.quality, "error": str(e)[-800:]})
        raise
    tag_video(args.folder, video)
    record(args.folder, video, args.quality)
    status_path.unlink(missing_ok=True)
    refreshed = refresh(args.folder)
    log(f"video ready: {video}" + (f" (refreshed {', '.join(p.name for p in refreshed)})" if refreshed else ""))
    print(json.dumps({"video_file": str(video), "video_quality": args.quality}))
    return 0


if __name__ == "__main__":
    run_main(main)

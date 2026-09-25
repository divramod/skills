#!/usr/bin/env python3
"""Prepare a video for summarizing: library folder, transcript, optional download + frames.

Steps (all deterministic; the agent only writes the summary afterwards):
  1. yt-dlp metadata -> folder <root>/<platform>/<user>/<title-slug>/ (reused by video id)
  2. download the video as video.<ext> in the highest available quality (mp4, or mkv when the
     best streams don't fit mp4) in a detached background process (download_video.py), so the
     transcript and summary don't wait for it; --skip-download keeps no video. [--visual]
     downloads in parallel with the transcript and waits for it (frames need the file); with
     --skip-download it fetches only a <=1080p copy for the frames
  3. transcript: captions (manual > auto, exactly one track), else local Whisper
     (mlx-whisper on Apple Silicon, openai-whisper elsewhere, via uvx; uses a finished
     video.<ext> if present, else a small audio-only download)
  4. [--visual] scene keyframes -> frames/ (extract_frames.py)
Writes transcript.md (with timestamp links) + metadata.json and prints one JSON object on stdout.

Root: $DM_SUMMARIZE_VIDEO_ROOT or ~/me/summaries/videos.
Requires: yt-dlp, ffmpeg; uvx only for the Whisper fallback.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import platform
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path

from _common import (BOT_HINT, SkillError, find_existing, find_file, fmt_ts, is_bot_error, log,
                     parse_ts, platform_of, probe_duration, read_json, require, run_main, ts_link, update_json,
                     user_of, video_dir, ytdlp_base)
from download_video import download, download_status, is_running, record, start_background, tag_video

PARAGRAPH_SECONDS = 30
MLX_MODEL = "mlx-community/whisper-large-v3-turbo"
OPENAI_MODEL = "turbo"
META_KEYS = ("id", "title", "channel", "uploader", "uploader_id", "upload_date", "duration",
             "webpage_url", "channel_url", "uploader_url", "extractor_key", "language", "chapters", "view_count", "tags", "description", "thumbnail")

# ---------------------------------------------------------------- pure helpers

_TAG_RE = re.compile(r"<[^>]+>")
_CUE_RE = re.compile(r"^(\d[\d:.,]*)\s+-->\s+(\d[\d:.,]*)")


def parse_vtt(text: str) -> list[tuple[float, str]]:
    """Parse WebVTT into (start_seconds, line) pairs.

    YouTube auto-captions "roll": each cue repeats the previous line plus the new
    words (with inline <c>/<timestamp> tags). We strip tags and emit a line only
    when it differs from the last emitted line, which removes the duplication.
    """
    out: list[tuple[float, str]] = []
    last = None
    start = None
    for raw in text.splitlines():
        line = raw.strip()
        m = _CUE_RE.match(line)
        if m:
            start = parse_ts(m.group(1))
            continue
        if start is None or not line or line.startswith(("NOTE", "STYLE", "REGION")):
            continue
        clean = html.unescape(_TAG_RE.sub("", line)).strip()
        if not clean or clean == last:
            continue
        out.append((start, clean))
        last = clean
    return out


def pick_track(info: dict, lang: str | None) -> tuple[str, bool] | None:
    """Choose exactly one caption track. Returns (lang_code, is_auto) or None.

    Preference: manual in wanted lang > manual in original lang > manual en > any manual,
    then auto '<orig>-orig' > auto orig > auto wanted > auto en. Requesting a single
    track matters: asking for many translated auto tracks triggers HTTP 429.
    """
    manual = {k: v for k, v in (info.get("subtitles") or {}).items() if k != "live_chat" and v}
    auto = {k: v for k, v in (info.get("automatic_captions") or {}).items() if v}
    orig = info.get("language")
    if not orig:
        orig_tracks = [k[: -len("-orig")] for k in auto if k.endswith("-orig")]
        orig = orig_tracks[0] if orig_tracks else None

    def first(cands, pool):
        for c in cands:
            if c and c in pool:
                return c
            if c:  # prefix match, e.g. "en" -> "en-US"
                for k in pool:
                    if k.split("-")[0] == c and not k.endswith("-orig"):
                        return k
        return None

    hit = first([lang, orig, "en"], manual) or (next(iter(manual)) if manual else None)
    if hit:
        return hit, False
    auto_cands = [f"{lang}-orig" if lang else None, lang, f"{orig}-orig" if orig else None, orig, "en"]
    if lang is None:  # prefer the spoken language when the caller has no preference
        auto_cands = [f"{orig}-orig" if orig else None, orig, "en"]
    hit = first(auto_cands, auto)
    return (hit, True) if hit else None


def group_paragraphs(lines, chapters=None, seconds=PARAGRAPH_SECONDS, link=fmt_ts) -> str:
    """Join (start, text) lines into timestamped paragraphs, split at chapter starts.

    `link(seconds)` renders each paragraph/chapter timestamp (plain mm:ss or a markdown link).
    """
    chapters = sorted(chapters or [], key=lambda c: c.get("start_time", 0))
    ch_idx = 0
    parts: list[str] = []
    para: list[str] = []
    para_start = 0.0

    def flush():
        if para:
            parts.append(f"[{link(para_start)}] " + " ".join(para))
            para.clear()

    for start, text in lines:
        heading = None
        while ch_idx < len(chapters) and start >= chapters[ch_idx].get("start_time", 0):
            heading = chapters[ch_idx]
            ch_idx += 1
        if heading:
            flush()
            parts.append(f"### {heading.get('title', 'Chapter')} ({link(heading.get('start_time', 0))})")
        if not para or start - para_start >= seconds:
            flush()
            para_start = start
        para.append(text)
    flush()
    return "\n\n".join(parts)


_URL_RE = re.compile(r"https?://[^\s<>()\[\]\"']+[^\s<>()\[\]\"'.,;:!?]")
_SLIDES_RE = re.compile(r"speakerdeck\.com|slideshare\.net|docs\.google\.com/presentation|slides\.com|pitch\.com|"
                        r"\.(pdf|pptx?|key)(\?|#|$)|/slides?\b", re.I)
_REPO_RE = re.compile(r"^https?://(www\.)?(github\.com|gitlab\.com|codeberg\.org|huggingface\.co)/[^/\s]+/[^/\s#?]+", re.I)
_NOISE_RE = re.compile(r"(youtube\.com|youtu\.be|instagram\.com|tiktok\.com|twitter\.com|x\.com|facebook\.com|"
                       r"linkedin\.com|patreon\.com|discord\.gg|discord\.com|bit\.ly/[a-z0-9]+$)", re.I)


def description_links(description: str | None) -> dict[str, list[str]]:
    """URLs from the video description, grouped: repos, slides, other (social/sponsor noise dropped)."""
    out: dict[str, list[str]] = {"repos": [], "slides": [], "other": []}
    for url in dict.fromkeys(_URL_RE.findall(description or "")):
        if _REPO_RE.match(url):
            out["repos"].append(url)
        elif _SLIDES_RE.search(url):
            out["slides"].append(url)
        elif not _NOISE_RE.search(url):
            out["other"].append(url)
    return out


def download_plan(skip_download: bool, visual: bool, have_quality: str | None, has_file: bool) -> tuple[str | None, str]:
    """(how, quality): how is 'background', 'wait' (frames need the file) or None (nothing to do)."""
    wanted = "1080p" if skip_download else "best"
    if visual:
        return "wait", wanted
    if skip_download or (has_file and have_quality == "best"):
        return None, wanted
    return "background", wanted


def render_transcript(info: dict, source: str, body: str) -> str:
    rows = [
        f"# {info.get('title', 'Untitled')}",
        "",
        f"- url: {info.get('webpage_url') or info.get('original_url') or ''}",
        f"- channel: {info.get('channel') or info.get('uploader') or '?'}",
        f"- published: {info.get('upload_date') or '?'}",
        f"- duration: {fmt_ts(info.get('duration') or 0)}",
        f"- platform: {platform_of(info)}",
        f"- transcript source: {source}",
    ]
    chapters = info.get("chapters") or []
    if chapters:
        rows += ["", "## Chapters", ""]
        rows += [f"- {ts_link(info, c.get('start_time', 0))} {c.get('title', '')}" for c in chapters]
    desc = (info.get("description") or "").strip()
    if desc:
        rows += ["", "## Description", "", desc[:2000]]
    rows += ["", "## Transcript", "", body, ""]
    return "\n".join(rows)


# ---------------------------------------------------------------- side effects


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def fetch_info(args) -> dict:
    p = run(ytdlp_base(args.cookies_from_browser) + ["--dump-single-json", "--skip-download", args.url])
    if p.returncode != 0:
        err = p.stderr.strip()
        raise SkillError(f"yt-dlp could not read metadata:\n{err}" + (f"\n{BOT_HINT}" if is_bot_error(err) else ""))
    return json.loads(p.stdout)


def fetch_captions(args, info: dict, folder: Path) -> tuple[list, str] | None:
    track = pick_track(info, args.lang)
    if not track:
        log("no caption track available")
        return None
    lang, is_auto = track
    log(f"downloading {'auto' if is_auto else 'manual'} captions [{lang}]")
    for f in folder.glob("subs*.vtt"):
        f.unlink()
    p = run(ytdlp_base(args.cookies_from_browser) + [
        "--skip-download", "--write-auto-subs" if is_auto else "--write-subs",
        "--sub-langs", lang, "--sub-format", "vtt/best", "--convert-subs", "vtt",
        "-o", str(folder / "subs.%(ext)s"), args.url])
    files = sorted(folder.glob("subs*.vtt"))
    if not files:
        log(f"caption download failed: {p.stderr.strip()[-300:]}")
        if is_bot_error(p.stderr):
            log(BOT_HINT)
        return None
    lines = parse_vtt(files[0].read_text(encoding="utf-8", errors="replace"))
    for f in files:
        f.unlink()
    if not lines:
        log("caption track was empty")
        return None
    return lines, f"captions ({'auto-generated' if is_auto else 'manual'}, {lang})"


def whisper_cmd(media: Path, out_dir: Path, lang: str | None) -> tuple[list[str], Path, str]:
    if sys.platform == "darwin" and platform.machine() == "arm64":
        engine = "mlx-whisper"
        cmd = ["uvx", "--from", "mlx-whisper", "mlx_whisper", str(media), "--model", MLX_MODEL,
               "--output-format", "json", "--output-dir", str(out_dir), "--output-name", "whisper",
               "--verbose", "False"]
        result = out_dir / "whisper.json"
    else:
        engine = "openai-whisper"
        cmd = ["uvx", "--from", "openai-whisper", "whisper", str(media), "--model", OPENAI_MODEL,
               "--output_format", "json", "--output_dir", str(out_dir)]
        result = out_dir / f"{media.stem}.json"
    if lang:
        cmd += ["--language", lang]
    return cmd, result, engine


def fetch_whisper(args, folder: Path, use_video: bool = True) -> tuple[list, str]:
    """Transcribe locally. `use_video=False` while video.<ext> is still downloading."""
    require("uvx")
    media = find_file(folder, "video") if use_video else None
    temp_audio = None
    if not media:
        log("downloading audio for Whisper transcription")
        p = run(ytdlp_base(args.cookies_from_browser) + ["-f", "bestaudio/best", "-o", str(folder / "audio.%(ext)s"), args.url])
        media = temp_audio = find_file(folder, "audio")
        if not media:
            err = p.stderr.strip()
            raise SkillError(f"audio download failed:\n{err[-800:]}" + (f"\n{BOT_HINT}" if is_bot_error(err) else ""))
    cmd, result, engine = whisper_cmd(media, folder, args.lang)
    log(f"transcribing {media.name} with {engine} (first run downloads the model, can take a while)")
    p = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0 or not result.exists():
        raise SkillError(f"whisper failed:\n{p.stderr.strip()[-800:]}")
    data = json.loads(result.read_text())
    result.unlink()
    if temp_audio and not args.keep_audio:
        temp_audio.unlink(missing_ok=True)
    lines = [(s["start"], s["text"].strip()) for s in data.get("segments", []) if s.get("text", "").strip()]
    return lines, f"whisper ({engine}, language={data.get('language', '?')})"


def fetch_transcript(args, info: dict, folder: Path, video_pending: bool) -> tuple[list, str]:
    result = None
    if args.source in ("auto", "captions"):
        result = fetch_captions(args, info, folder)
    if result is None and args.source == "captions":
        raise SkillError("no usable captions (try --source whisper)")
    return result or fetch_whisper(args, folder, use_video=not video_pending)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--skip-download", action="store_true",
                    help="don't download the video (default: best quality, in the background)")
    ap.add_argument("--visual", action="store_true",
                    help="extract keyframes (waits for the download; <=1080p with --skip-download)")
    ap.add_argument("--max-frames", type=int, default=40)
    ap.add_argument("--lang", help="preferred transcript language (e.g. en, de); default: spoken language")
    ap.add_argument("--source", choices=["auto", "captions", "whisper"], default="auto",
                    help="auto = captions, Whisper fallback (default)")
    ap.add_argument("--cookies-from-browser", default=os.environ.get("DM_SUMMARIZE_VIDEO_BROWSER"),
                    help="pass browser cookies to yt-dlp (chrome, firefox, safari, ...)")
    ap.add_argument("--refresh", action="store_true", help="refetch the transcript even if it exists")
    ap.add_argument("--keep-audio", action="store_true", help="keep the audio file downloaded for Whisper")
    args = ap.parse_args(argv)

    require("yt-dlp", "ffmpeg")
    info = fetch_info(args)
    existing = find_existing(info)
    folder = existing or video_dir(info)
    folder.mkdir(parents=True, exist_ok=True)
    log(f"{'reusing' if existing else 'folder'}: {folder}")

    old_meta = read_json(folder / "metadata.json")
    have_quality = old_meta.get("video_quality")
    transcript = folder / "transcript.md"
    source = old_meta.get("transcript_source")
    need_transcript = args.refresh or not (transcript.exists() and source)
    if not need_transcript:
        log("using existing transcript (pass --refresh to refetch)")

    # Title, chapters etc. first: the download tags the file from metadata.json when it finishes.
    update_json(folder / "metadata.json", {k: info.get(k) for k in META_KEYS})
    # Default: detached background download, nothing here waits for it.
    # --visual: frames need the file, so download in parallel with the transcript and wait.
    how, wanted = download_plan(args.skip_download, args.visual, have_quality, find_file(folder, "video") is not None)
    background = video_future = None
    pool = ThreadPoolExecutor(max_workers=1)
    if how == "wait":
        video_future = pool.submit(download, folder, args.url, wanted, have_quality, args.cookies_from_browser)
    elif how == "background":
        background = start_background(folder, args.url, wanted, have_quality, args.cookies_from_browser)

    try:
        if need_transcript:
            lines, source = fetch_transcript(args, info, folder, video_pending=bool(background or video_future))
            body = group_paragraphs(lines, info.get("chapters"), link=lambda s: ts_link(info, s))
            transcript.write_text(render_transcript(info, source, body), encoding="utf-8")
        if video_future:
            record(folder, video_future.result(), "best" if have_quality == "best" else wanted)
    finally:
        pool.shutdown(wait=True)

    # Merge, don't overwrite: a background download may add video_file/video_quality at any time.
    meta = update_json(folder / "metadata.json", {k: info.get(k) for k in META_KEYS} | {
        "platform": platform_of(info),
        "user": user_of(info),
        "transcript_source": source,
        "prepared": old_meta.get("prepared") or date.today().isoformat(),
        "prepared_at": old_meta.get("prepared_at") or datetime.now().isoformat(timespec="seconds"),
    })
    video = folder / meta["video_file"] if meta.get("video_file") else None
    video = video if video and video.exists() and not is_running(folder) else None
    if video_future and video:
        tag_video(folder, video)  # after the metadata write: a new folder has no title before it
    if video and not meta.get("duration"):
        info["duration"] = probe_duration(video)
        update_json(folder / "metadata.json", {"duration": info["duration"]})

    frames_index = None
    if args.visual:
        from extract_frames import extract
        frames_index = extract(folder, max_frames=args.max_frames)
    elif (folder / "frames" / "index.md").exists():
        frames_index = folder / "frames" / "index.md"

    summary = folder / "summary.md"
    out = {
        "dir": str(folder),
        "reused": bool(existing),
        "id": info.get("id"),
        "title": info.get("title"),
        "channel": info.get("channel") or info.get("uploader"),
        "platform": platform_of(info),
        "duration": fmt_ts(info.get("duration") or 0),
        "chapters": len(info.get("chapters") or []),
        "transcript": str(transcript),
        "transcript_source": source,
        "transcript_words": len(transcript.read_text(encoding="utf-8").split()),
        "video_file": str(video) if video else None,
        "video_download": download_status(folder),
        "frames_index": str(frames_index) if frames_index else None,
        "description_links": description_links(info.get("description")),
        "summary": str(summary),
        "summary_exists": summary.exists(),
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    run_main(main)

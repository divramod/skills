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
Writes content.md (the transcript, with timestamp links) + metadata.json (the shared contract fields plus the
yt-dlp keys) and prints the source envelope on stdout. A playlist or channel URL is handed to
list_videos.py (--limit N) and prints its video list instead.

Folder: <root>/videos/<platform>/<user>/<title>/ (root: $TELL_ROOT or ~/skills/tell).

As a part of another source's item (an x post's video): --dir <folder> --content-part <name> writes into that
folder instead, keeps the transcript as <name>-transcript.md, stores the video's facts under metadata.json's
<name> key (the other source owns the contract fields; the download still records video_file/video_quality) and
prints {part, transcript, transcript_source, ...} instead of an envelope. No videos/… library entry is made. The
folder must already hold the owner's metadata.json (source and title). The part's transcript is reused unless
--refresh or the part now comes from another URL / playlist item.

A post with several videos is a playlist to yt-dlp even with --no-playlist (its top level has no duration or
captions): the video is entry --playlist-item N (default 1), and every later yt-dlp call gets --playlist-items N.
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

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

from _common import (BOT_HINT, SkillError, browser_cookies, envelope, find_existing, find_file, fmt_date, fmt_ts,
                     is_bot_error, log, parse_ts, platform_of, probe_duration, read_json, require, run_main, ts_link,
                     update_json, user_of, video_dir, ytdlp_base)
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


def pick_entry(info: dict, item: int) -> tuple[dict, int | None, int]:
    """(the video's info, the yt-dlp playlist item or None, how many videos the URL holds). A single-item URL that
    yt-dlp answers as a playlist (an x post with several videos) gives entry `item` (1-based; the first when out of
    range), with the post's facts it lacks."""
    if info.get("_type") != "playlist":
        return info, None, 1
    entries = [e for e in info.get("entries") or [] if isinstance(e, dict)]
    if not entries:
        raise SkillError(f"yt-dlp found no video in {info.get('webpage_url') or info.get('original_url')}")
    n = item if 1 <= item <= len(entries) else 1
    if n != item:
        log(f"there is no video {item} (the URL has {len(entries)}); taking video 1")
    entry = dict(entries[n - 1])
    for k in ("webpage_url", "original_url", "uploader", "uploader_id", "channel", "upload_date", "description"):
        if not entry.get(k) and info.get(k):
            entry[k] = info[k]
    return entry, n, len(entries)


def render_transcript(info: dict, source: str, body: str) -> str:
    rows = [
        f"# {info.get('title', 'Untitled')}",
        "",
        f"- url: {info.get('webpage_url') or info.get('original_url') or ''}",
        f"- channel: {info.get('channel') or info.get('uploader') or '?'}",
        f"- published: {info.get('upload_date') or '?'}",
        f"- duration: {fmt_ts(info['duration']) if info.get('duration') else '?'}",
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


def contract_fields(info: dict, source: str | None, fetched: str, transcript: Path) -> dict:
    """The shared metadata.json fields (see _common.CONTRACT_KEYS) for a video."""
    return {
        "source": "video",
        "url": info.get("webpage_url") or info.get("original_url"),
        "author": info.get("channel") or info.get("uploader"),
        "published": fmt_date(info.get("upload_date")),
        "fetched": fetched,
        "site": platform_of(info),
        "word_count": len(transcript.read_text(encoding="utf-8").split()) if transcript.exists() else 0,
        "extractor": source,
        "content_file": transcript.name,
        "extras": {"views": info.get("view_count"), "chapters": len(info.get("chapters") or [])},
    }


# ---------------------------------------------------------------- side effects


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def ytdlp(args) -> list[str]:
    """yt-dlp with the cookies and, for one video of a playlist-shaped URL, --playlist-items."""
    item = getattr(args, "item", None)
    return ytdlp_base(args.cookies_from_browser) + (["--playlist-items", str(item)] if item else [])


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
    p = run(ytdlp(args) + [
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
        p = run(ytdlp(args) + ["-f", "bestaudio/best", "-o", str(folder / "audio.%(ext)s"), args.url])
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
    ap.add_argument("--cookies-from-browser", default=browser_cookies(),
                    help="pass browser cookies to yt-dlp (chrome, firefox, safari, ...)")
    ap.add_argument("--refresh", action="store_true", help="refetch the transcript even if it exists")
    ap.add_argument("--keep-audio", action="store_true", help="keep the audio file downloaded for Whisper")
    ap.add_argument("--limit", type=int, help="playlist/channel URLs: max videos (channels default to 10)")
    ap.add_argument("--dir", type=Path, help="with --content-part: the other source's folder to write into")
    ap.add_argument("--content-part", metavar="NAME",
                    help="prepare the video as part NAME of another item (needs --dir; see above)")
    ap.add_argument("--playlist-item", type=int, default=1, metavar="N",
                    help="a URL with several videos (an x post): take video N (default 1)")
    args = ap.parse_args(argv)
    if bool(args.dir) != bool(args.content_part):
        raise SkillError("--dir and --content-part go together")

    if not args.url.startswith(("http://", "https://")):
        raise SkillError(f"local media files are not supported yet: {args.url}")
    from route import route
    if not args.content_part and route(args.url)["kind"] in ("playlist", "channel"):
        import list_videos
        return list_videos.main([args.url] + (["--limit", str(args.limit)] if args.limit else []) + (
            ["--cookies-from-browser", args.cookies_from_browser] if args.cookies_from_browser else []))

    part = args.content_part
    if part:  # the owner's fields come first: the download and the page refresh read them
        owner = read_json(args.dir / "metadata.json")
        if not (owner.get("source") and owner.get("title")):
            raise SkillError(f"--content-part needs --dir to be a prepared item's folder (metadata.json with "
                             f"source and title): {args.dir}")
    require("yt-dlp", "ffmpeg")
    info, args.item, videos = pick_entry(fetch_info(args), args.playlist_item)
    if videos > 1:
        log(f"{args.url} has {videos} videos; taking video {args.item}")
    if part:
        existing, folder = None, args.dir
    else:
        existing = find_existing(info)
        folder = existing or video_dir(info)
    folder.mkdir(parents=True, exist_ok=True)
    log(f"{'reusing' if existing else 'folder'}: {folder}")
    if existing:  # a folder from before the multi-source layout keeps its transcript
        from migrate_library import migrate_folder
        if (done := migrate_folder(folder)) and done.get("actions"):
            log(f"migrated to the multi-source layout: {', '.join(done['actions'])}")

    old_meta = read_json(folder / "metadata.json")
    have_quality = old_meta.get("video_quality")
    transcript = folder / (f"{part}-transcript.md" if part else "content.md")
    source = (old_meta.get(part) or {}).get("transcript_source") if part else old_meta.get("transcript_source")
    need_transcript = args.refresh or not (transcript.exists() and source) or (part and moved(old_meta.get(part), args))
    if not need_transcript:
        # a part runs under its owner's script, which names the flag that reaches --refresh here (x: --refresh-video)
        log("using existing transcript (pass --refresh to refetch)" if not part
            else f"using the existing {part} transcript (the owning source's refresh flag refetches it)")

    # Title, chapters etc. first: the download tags the file from metadata.json when it finishes.
    if not part:  # a part: the owning source wrote its title already
        update_json(folder / "metadata.json", {k: info.get(k) for k in META_KEYS})
    # Default: detached background download, nothing here waits for it.
    # --visual: frames need the file, so download in parallel with the transcript and wait.
    how, wanted = download_plan(args.skip_download, args.visual, have_quality, find_file(folder, "video") is not None)
    background = video_future = None
    pool = ThreadPoolExecutor(max_workers=1)
    if how == "wait":
        video_future = pool.submit(download, folder, args.url, wanted, have_quality, args.cookies_from_browser,
                                   None, args.item)
    elif how == "background":
        background = start_background(folder, args.url, wanted, have_quality, args.cookies_from_browser, args.item)

    try:
        if need_transcript:
            lines, source = fetch_transcript(args, info, folder, video_pending=bool(background or video_future))
            body = group_paragraphs(lines, info.get("chapters"), link=lambda s: ts_link(info, s))
            transcript.write_text(render_transcript(info, source, body), encoding="utf-8")
        if video_future:
            record(folder, video_future.result(), "best" if have_quality == "best" else wanted)
    finally:
        pool.shutdown(wait=True)

    if part:
        return print_part(folder, part, info, transcript, source, video_future, args, videos)

    # Merge, don't overwrite: a background download may add video_file/video_quality at any time.
    prepared_at = old_meta.get("prepared_at") or datetime.now().isoformat(timespec="seconds")
    meta = update_json(folder / "metadata.json", {k: info.get(k) for k in META_KEYS} | {
        "platform": platform_of(info),
        "user": user_of(info),
        "transcript_source": source,
        "prepared": old_meta.get("prepared") or date.today().isoformat(),
        "prepared_at": prepared_at,
    } | contract_fields(info, source, prepared_at, transcript))
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

    out = envelope(folder, meta, "video",
        reused=bool(existing),
        channel=info.get("channel") or info.get("uploader"),
        platform=platform_of(info),
        duration=fmt_ts(info.get("duration") or 0),
        chapters=len(info.get("chapters") or []),
        transcript=str(transcript),
        transcript_source=source,
        transcript_words=len(transcript.read_text(encoding="utf-8").split()),
        video_file=str(video) if video else None,
        video_download=download_status(folder),
        frames_index=str(frames_index) if frames_index else None,
        description_links=description_links(info.get("description")),
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def moved(old_part: dict | None, args) -> bool:
    """True when the stored part came from another URL or playlist item (its transcript is not this video's)."""
    if not old_part:
        return False
    was = old_part.get("source_url") or old_part.get("webpage_url")
    return bool(was and was != args.url) or (old_part.get("playlist_item") or 1) != (args.item or 1)


def print_part(folder: Path, part: str, info: dict, transcript: Path, source: str | None, video_future,
               args, videos: int = 1) -> int:
    """--content-part: the video's facts under metadata.json's <part> key, then the part JSON on stdout."""
    facts = {k: info.get(k) for k in ("id", "title", "duration", "webpage_url", "upload_date", "extractor_key")}
    facts |= {"source_url": args.url, "playlist_item": args.item, "videos": videos}
    meta = update_json(folder / "metadata.json", {part: facts | {"transcript_source": source,
                                                                 "transcript_file": transcript.name}})
    video = folder / meta["video_file"] if meta.get("video_file") else None
    video = video if video and video.exists() and not is_running(folder) else None
    if video_future and video:
        tag_video(folder, video)
    frames_index = None
    if args.visual:
        from extract_frames import extract
        frames_index = extract(folder, max_frames=args.max_frames)
    out = {"part": part, "dir": str(folder), "title": info.get("title"), "url": info.get("webpage_url"),
           "duration": fmt_ts(info["duration"]) if info.get("duration") else None,
           "duration_seconds": info.get("duration"), "videos": videos, "playlist_item": args.item,
           "transcript": str(transcript),
           "transcript_source": source, "transcript_words": len(transcript.read_text(encoding="utf-8").split()),
           "video_file": str(video) if video else None, "video_download": download_status(folder),
           "frames_index": str(frames_index) if frames_index else None}
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    run_main(main)

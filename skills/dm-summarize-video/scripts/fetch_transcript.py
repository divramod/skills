#!/usr/bin/env python3
"""Fetch a timestamped transcript for a video URL, ready for an LLM to summarize.

Strategy (method B of docs/research/0002-summarize-video):
  1. yt-dlp captions: manual subtitles first, then auto-captions, exactly one track.
  2. Fallback: download audio with yt-dlp and transcribe locally with Whisper
     (mlx-whisper on Apple Silicon, openai-whisper elsewhere), both run via `uvx`.

Output: <out>/transcript.md (header + chapters + timestamped paragraphs) and
<out>/metadata.json. The transcript path is printed as the last stdout line.
Results are cached per video; pass --refresh to refetch.

Stdlib only. Requires: yt-dlp, ffmpeg; uv (only for the Whisper fallback).
"""
from __future__ import annotations

import argparse
import html
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

CACHE_ROOT = Path(os.environ.get("DM_SUMMARIZE_VIDEO_CACHE", Path.home() / ".cache" / "dm-summarize-video"))
PARAGRAPH_SECONDS = 30
MLX_MODEL = "mlx-community/whisper-large-v3-turbo"
OPENAI_MODEL = "turbo"
BOT_HINT = (
    "YouTube bot check / rate limit hit. Retry with --cookies-from-browser chrome "
    "(or firefox/safari), wait a few minutes, or update yt-dlp: brew upgrade yt-dlp"
)


class FetchError(RuntimeError):
    pass


def log(msg: str) -> None:
    print(f"[dm-summarize-video] {msg}", file=sys.stderr)


# ---------------------------------------------------------------- pure helpers


def fmt_ts(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def parse_ts(ts: str) -> float:
    parts = ts.replace(",", ".").split(":")
    secs = 0.0
    for p in parts:
        secs = secs * 60 + float(p)
    return secs


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


def group_paragraphs(lines, chapters=None, seconds=PARAGRAPH_SECONDS) -> str:
    """Join (start, text) lines into timestamped paragraphs, split at chapter starts."""
    chapters = sorted(chapters or [], key=lambda c: c.get("start_time", 0))
    ch_idx = 0
    parts: list[str] = []
    para: list[str] = []
    para_start = 0.0

    def flush():
        if para:
            parts.append(f"[{fmt_ts(para_start)}] " + " ".join(para))
            para.clear()

    for start, text in lines:
        heading = None
        while ch_idx < len(chapters) and start >= chapters[ch_idx].get("start_time", 0):
            heading = chapters[ch_idx]
            ch_idx += 1
        if heading:
            flush()
            parts.append(f"### {heading.get('title', 'Chapter')} ({fmt_ts(heading.get('start_time', 0))})")
        if not para or start - para_start >= seconds:
            flush()
            para_start = start
        para.append(text)
    flush()
    return "\n\n".join(parts)


def render_markdown(info: dict, source: str, body: str) -> str:
    url = info.get("webpage_url") or info.get("original_url") or ""
    rows = [
        f"# {info.get('title', 'Untitled')}",
        "",
        f"- url: {url}",
        f"- channel: {info.get('channel') or info.get('uploader') or '?'}",
        f"- published: {info.get('upload_date') or '?'}",
        f"- duration: {fmt_ts(info.get('duration') or 0)}",
        f"- platform: {info.get('extractor_key') or '?'}",
        f"- transcript source: {source}",
    ]
    chapters = info.get("chapters") or []
    if chapters:
        rows += ["", "## Chapters", ""]
        rows += [f"- {fmt_ts(c.get('start_time', 0))} {c.get('title', '')}" for c in chapters]
    desc = (info.get("description") or "").strip()
    if desc:
        rows += ["", "## Description", "", desc[:2000]]
    rows += ["", "## Transcript", "", body, ""]
    return "\n".join(rows)


# ---------------------------------------------------------------- side effects


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def ytdlp_base(args) -> list[str]:
    cmd = ["yt-dlp", "--no-playlist", "--no-warnings"]
    if args.cookies_from_browser:
        cmd += ["--cookies-from-browser", args.cookies_from_browser]
    return cmd


def fetch_info(args) -> dict:
    p = run(ytdlp_base(args) + ["--dump-single-json", "--skip-download", args.url])
    if p.returncode != 0:
        err = p.stderr.strip()
        hint = f"\n{BOT_HINT}" if re.search(r"not a bot|429|Sign in", err) else ""
        raise FetchError(f"yt-dlp could not read metadata:\n{err}{hint}")
    return json.loads(p.stdout)


def fetch_captions(args, info: dict, work: Path) -> tuple[list, str] | None:
    track = pick_track(info, args.lang)
    if not track:
        log("no caption track available")
        return None
    lang, is_auto = track
    log(f"downloading {'auto' if is_auto else 'manual'} captions [{lang}]")
    for f in work.glob("subs*.vtt"):
        f.unlink()
    cmd = ytdlp_base(args) + [
        "--skip-download",
        "--write-auto-subs" if is_auto else "--write-subs",
        "--sub-langs", lang,
        "--sub-format", "vtt/best",
        "--convert-subs", "vtt",
        "-o", str(work / "subs.%(ext)s"),
        args.url,
    ]
    p = run(cmd)
    files = sorted(work.glob("subs*.vtt"))
    if not files:
        log(f"caption download failed: {p.stderr.strip()[-500:]}")
        if re.search(r"not a bot|429", p.stderr):
            log(BOT_HINT)
        return None
    lines = parse_vtt(files[0].read_text(encoding="utf-8", errors="replace"))
    if not lines:
        log("caption track was empty")
        return None
    return lines, f"captions ({'auto-generated' if is_auto else 'manual'}, {lang})"


def whisper_cmd(audio: Path, out_dir: Path, lang: str | None) -> tuple[list[str], Path]:
    if sys.platform == "darwin" and platform.machine() == "arm64":
        cmd = ["uvx", "--from", "mlx-whisper", "mlx_whisper", str(audio),
               "--model", MLX_MODEL, "--output-format", "json",
               "--output-dir", str(out_dir), "--output-name", "whisper", "--verbose", "False"]
    else:
        cmd = ["uvx", "--from", "openai-whisper", "whisper", str(audio),
               "--model", OPENAI_MODEL, "--output_format", "json", "--output_dir", str(out_dir)]
    if lang:
        cmd += ["--language", lang]
    name = "whisper.json" if cmd[2] == "mlx-whisper" else f"{audio.stem}.json"
    return cmd, out_dir / name


def fetch_whisper(args, work: Path) -> tuple[list, str]:
    if not shutil.which("uvx"):
        raise FetchError("Whisper fallback needs `uv` (https://docs.astral.sh/uv/).")
    log("downloading audio for Whisper transcription")
    p = run(ytdlp_base(args) + ["-f", "bestaudio/best", "-o", str(work / "audio.%(ext)s"), args.url])
    audio = next((f for f in work.glob("audio.*") if f.suffix not in (".part", ".ytdl")), None)
    if not audio:
        hint = f"\n{BOT_HINT}" if re.search(r"not a bot|429", p.stderr) else ""
        raise FetchError(f"audio download failed:\n{p.stderr.strip()[-800:]}{hint}")
    cmd, result = whisper_cmd(audio, work, args.lang)
    log(f"transcribing with {cmd[2]} (first run downloads the model, can take a while)")
    p = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0 or not result.exists():
        raise FetchError(f"whisper failed:\n{p.stderr.strip()[-800:]}")
    data = json.loads(result.read_text())
    lines = [(s["start"], s["text"].strip()) for s in data.get("segments", []) if s.get("text", "").strip()]
    if not args.keep_audio:
        audio.unlink(missing_ok=True)
    return lines, f"whisper ({cmd[2]}, language={data.get('language', '?')})"


def cache_dir(info: dict) -> Path:
    key = f"{(info.get('extractor_key') or 'video').lower()}-{info.get('id') or 'unknown'}"
    return CACHE_ROOT / re.sub(r"[^A-Za-z0-9._-]", "_", key)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--lang", help="preferred transcript language (e.g. en, de); default: spoken language")
    ap.add_argument("--source", choices=["auto", "captions", "whisper"], default="auto",
                    help="auto = captions, Whisper fallback (default)")
    ap.add_argument("--cookies-from-browser", default=os.environ.get("DM_SUMMARIZE_VIDEO_BROWSER"),
                    help="pass browser cookies to yt-dlp (chrome, firefox, safari, ...)")
    ap.add_argument("--out", type=Path, help="output dir (default: cache dir per video)")
    ap.add_argument("--refresh", action="store_true", help="ignore cached transcript")
    ap.add_argument("--keep-audio", action="store_true", help="keep downloaded audio file")
    args = ap.parse_args(argv)

    for tool in ("yt-dlp", "ffmpeg"):
        if not shutil.which(tool):
            log(f"missing dependency: {tool} (brew install {tool})")
            return 2
    try:
        info = fetch_info(args)
        work = args.out or cache_dir(info)
        work.mkdir(parents=True, exist_ok=True)
        transcript = work / "transcript.md"
        if transcript.exists() and not args.refresh:
            log("using cached transcript (pass --refresh to refetch)")
            print(transcript)
            return 0

        result = None
        if args.source in ("auto", "captions"):
            result = fetch_captions(args, info, work)
        if result is None and args.source == "captions":
            raise FetchError("no usable captions (try --source whisper)")
        if result is None:
            result = fetch_whisper(args, work)
        lines, source = result

        body = group_paragraphs(lines, info.get("chapters"))
        transcript.write_text(render_markdown(info, source, body), encoding="utf-8")
        meta_keys = ("id", "title", "channel", "uploader", "upload_date", "duration", "webpage_url",
                     "extractor_key", "language", "chapters", "view_count", "tags")
        meta = {k: info.get(k) for k in meta_keys} | {"transcript_source": source}
        (work / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        words = len(body.split())
        log(f"ok: {source}, {len(lines)} lines, ~{words} words")
        print(transcript)
        return 0
    except FetchError as e:
        log(str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())

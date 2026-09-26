#!/usr/bin/env python3
"""Read a library folder's note aloud: summary.md (or digest.md) -> summary.m4a (digest.m4a) next to it.

Local text-to-speech with Supertonic-3 (tts_supertonic.py, run via `uv run --script`: no system libraries on
macOS, Linux or Windows; the ~385 MB model downloads once into <library root>/.models/supertonic-3). The text is
the note without its links sections, URLs and anchor links (shared/speech_text.py). ffmpeg, when installed,
compresses the WAV to AAC (.m4a); without it the .wav stays. The page's "Read aloud" button starts this through
serve_library.py (--background) and polls --status; the finished recording is recorded in metadata.json
(speech_file, speech_hash of the text it was made from, speech_voice) and the page is re-rendered with a player.
While it runs, `.speech.json` in the folder holds {status: running, pid, progress, parts, total} and every finished
paragraph is in `.speech-parts/<i>.wav` (the page plays them while the rest is recorded); {status: failed, error} on
failure. Both are removed on success.

Usage: speak.py <folder> [--voice F1] [--lang de]   (record now, in the foreground)
       speak.py <folder> --background              (start detached, print the status)
       speak.py <folder> --status                  (JSON: {status: none|running|failed|done|stale, progress, audio, error};
                                                    running: parts ready so far, total, parts_dir)
       speak.py <folder> --text                    (print the text that would be read)
       speak.py --warm                             (install the engine and download the model now)
Voices: F1-F5, M1-M5 ($TELL_VOICE sets the default). The language is the note's `lang` (else en).
Requires: uv; ffmpeg optional.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

from _common import SkillError, env, library_root, log, read_json, require, run_main, update_json, write_json
from library import root_of
from render_html import split_frontmatter
from speech_text import speech_text, text_hash

HERE = Path(__file__).resolve().parent
ENGINE = HERE / "tts_supertonic.py"
STATUS_FILE = ".speech.json"
PARTS_DIR = ".speech-parts"
DEFAULT_VOICE = env("TELL_VOICE") or "F1"


def note_of(folder: Path) -> Path:
    meta = read_json(folder / "metadata.json")
    note = folder / ("digest.md" if meta.get("kind") == "digest" else "summary.md")
    if not note.exists():
        raise SkillError(f"{note} missing: save the summary first")
    return note


def models_dir(folder: Path | None = None) -> Path:
    """Where the engine keeps its model: under the library root (a skill's own data lives there)."""
    root = (root_of(folder) if folder else None) or library_root()
    return root / ".models" / "supertonic-3"


def pid_alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError, TypeError):
        return False
    return True


def status(folder: Path) -> dict:
    """{status, progress, audio, error}: running (+ parts, total, parts_dir) / failed from .speech.json, else done (the
    recording matches the note), stale (the note changed since) or none."""
    run = read_json(folder / STATUS_FILE)
    if run.get("status") == "running":
        if pid_alive(run.get("pid")):
            return {"status": "running", "progress": run.get("progress"), "parts": run.get("parts", 0),
                    "total": run.get("total"), "parts_dir": PARTS_DIR}
        return {"status": "failed", "error": "the recording process exited unexpectedly"}
    if run.get("status") == "failed":
        return {"status": "failed", "error": run.get("error")}
    meta = read_json(folder / "metadata.json")
    audio = meta.get("speech_file")
    if not audio or not (folder / audio).exists():
        return {"status": "none"}
    current = meta.get("speech_hash") == text_hash(speech_text(note_of(folder).read_text(encoding="utf-8")))
    return {"status": "done" if current else "stale", "audio": audio}


def start_background(folder: Path, voice: str | None, lang: str | None) -> dict:
    """Start this script detached; returns the status (unchanged when running or already current)."""
    state = status(folder)
    if state["status"] in ("running", "done"):
        return state
    note_of(folder)  # fail now, not in the background
    cmd = [sys.executable, str(Path(__file__).resolve()), str(folder)]
    cmd += ["--voice", voice] if voice else []
    cmd += ["--lang", lang] if lang else []
    log_path = folder / ".speech.log"
    with open(log_path, "w") as logf:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=logf, stderr=logf, start_new_session=True)
    write_json(folder / STATUS_FILE, {"status": "running", "pid": proc.pid, "log": str(log_path),
                                      "started": datetime.now().isoformat(timespec="seconds")})
    log(f"recording started in the background (pid {proc.pid}, log {log_path})")
    return {"status": "running", "progress": None}


def engine_cmd(*args: str) -> list[str]:
    return ["uv", "run", "--quiet", "--script", str(ENGINE), *args]


def engine_env(folder: Path | None) -> dict:
    return {**os.environ, "SUPERTONIC_CACHE_DIR": str(models_dir(folder)), "SUPERTONIC_LOG_LEVEL": "WARNING"}


def synthesize(folder: Path, text: str, out: Path, voice: str, lang: str, progress) -> None:
    """Run the engine on text into out (WAV) and each paragraph into .speech-parts/<i>.wav; calls
    progress({total}) at the start and progress({parts, progress}) as paragraphs finish."""
    text_file = folder / ".speech.txt"
    text_file.write_text(text, encoding="utf-8")
    err_file = folder / ".speech.err"
    parts = folder / PARTS_DIR
    shutil.rmtree(parts, ignore_errors=True)
    parts.mkdir()
    try:
        with open(err_file, "w") as errf:
            with subprocess.Popen(engine_cmd(str(text_file), str(out), "--parts", str(parts), "--lang", lang,
                                             "--voice", voice),
                                  stdout=subprocess.PIPE, stderr=errf, text=True, env=engine_env(folder)) as proc:
                for line in proc.stdout or ():
                    word = line.split()
                    if word[:1] == ["PARTS"]:
                        progress({"total": int(word[1])})
                    elif word[:1] == ["PART"]:
                        progress({"parts": int(word[1]), "progress": float(word[2])})
            code = proc.returncode
        if code != 0 or not out.exists():
            tail = err_file.read_text(errors="replace").strip().splitlines()[-5:]
            raise SkillError("text-to-speech failed: " + (" | ".join(tail) or f"exit {code}"))
    finally:
        text_file.unlink(missing_ok=True)
        err_file.unlink(missing_ok=True)
        shutil.rmtree(parts, ignore_errors=True)


def compress(wav: Path) -> Path:
    """WAV -> AAC .m4a (a tenth of the size) when ffmpeg is installed; else the WAV."""
    if not shutil.which("ffmpeg"):
        return wav
    m4a = wav.with_suffix(".m4a")
    p = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-ac", "1", "-c:a", "aac", "-b:a", "64k",
                        "-movflags", "+faststart", str(m4a)], capture_output=True, text=True)
    if p.returncode != 0:
        log(f"ffmpeg could not compress the recording, keeping the WAV: {p.stderr.strip()[-300:]}")
        m4a.unlink(missing_ok=True)
        return wav
    wav.unlink()
    return m4a


def record(folder: Path, voice: str, lang: str | None) -> Path:
    """Record the note now; returns the audio file."""
    require("uv")
    note = note_of(folder)
    note_text = note.read_text(encoding="utf-8")
    text = speech_text(note_text)
    if not text.strip():
        raise SkillError(f"{note} has no text to read")
    lang = lang or split_frontmatter(note_text)[0].get("lang") or "en"
    status_path = folder / STATUS_FILE
    run = read_json(status_path)
    if run.get("pid") != os.getpid():  # started by hand, not via start_background
        run = {"status": "running", "pid": os.getpid()}
        write_json(status_path, run)
    wav = folder / f".{note.stem}.speech.wav"
    try:
        def progress(fields: dict) -> None:
            run.update(fields)
            write_json(status_path, run)

        synthesize(folder, text, wav, voice, lang, progress)
        final = compress(wav)
        audio = final.with_name(note.stem + final.suffix)
        for old in folder.glob(f"{note.stem}.m4a"), folder.glob(f"{note.stem}.wav"):
            for f in old:
                f.unlink()
        final.rename(audio)
    except BaseException as e:
        wav.unlink(missing_ok=True)
        write_json(status_path, {"status": "failed", "error": str(e)[-800:] or type(e).__name__})
        raise
    update_json(folder / "metadata.json", {"speech_file": audio.name, "speech_hash": text_hash(text),
                                           "speech_voice": voice, "speech_engine": "supertonic-3"})
    status_path.unlink(missing_ok=True)
    from render_html import write as write_html
    write_html(folder)
    return audio


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path, nargs="?")
    ap.add_argument("--voice", help=f"F1-F5 or M1-M5 (default {DEFAULT_VOICE}, $TELL_VOICE)")
    ap.add_argument("--lang", help="language of the note (default: its frontmatter lang, else en)")
    ap.add_argument("--status", action="store_true", help="print the recording's status as JSON")
    ap.add_argument("--background", action="store_true", help="record detached and print the status")
    ap.add_argument("--text", action="store_true", help="print the text that would be read")
    ap.add_argument("--warm", action="store_true", help="install the engine and download the model now")
    args = ap.parse_args(argv)
    if args.warm:
        require("uv")
        p = subprocess.run(engine_cmd("--warm"), env=engine_env(args.folder))
        return p.returncode
    if not args.folder:
        ap.error("folder is required unless --warm is given")
    if args.status:
        print(json.dumps(status(args.folder)))
        return 0
    if args.text:
        print(speech_text(note_of(args.folder).read_text(encoding="utf-8")))
        return 0
    if args.background:
        print(json.dumps(start_background(args.folder, args.voice, args.lang)))
        return 0
    audio = record(args.folder, args.voice or DEFAULT_VOICE, args.lang)
    log(f"recording ready: {audio}")
    print(json.dumps({"status": "done", "audio": str(audio)}))
    return 0


if __name__ == "__main__":
    run_main(main)

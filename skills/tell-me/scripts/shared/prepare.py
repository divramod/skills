#!/usr/bin/env python3
"""Prepare any input for summarizing: route it to its source, run scripts/<source>/prepare.py.

route.py picks the source (video, web, github, x, hn, file); the source script fetches the content
into its library folder (content file with anchor links + metadata.json) and prints the envelope.
This script checks the envelope and prints it unchanged, so the agent reads `subskill` and
`template` next. Every flag after the input goes to the source script (e.g. --skip-download,
--visual, --lang for video). Exit codes pass through: 1 expected error, 2 missing tool (the
message names the source's install-prerequisites.sh).

Several inputs (every argument before the first flag) are prepared one after the other; each source gets only
the flags its script knows. A failing input doesn't stop the others. It prints {kind: "inputs", items: [one
envelope per input, or {input, error, exit_code}], digest_dir}: the digest folder <root>/digests/<date>-<slug>/
is made when at least two inputs worked. Exit 0 when at least one input worked.

Usage: prepare.py "<url-or-path>" ["<url-or-path>" ...] [source flags]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from functools import lru_cache
from pathlib import Path

from _common import ENVELOPE_KEYS, SkillError, digest_dir, is_legacy, log, read_json, run_main, source_root
from route import route

SOURCES_DIR = Path(__file__).resolve().parent.parent  # scripts/
LIST_KINDS = ("playlist", "channel")


def dispatch(text: str, flags: list[str], sources_dir: Path = SOURCES_DIR,
             errors: list[str] | None = None) -> tuple[int, dict | None]:
    """(exit code, envelope). The source script's progress goes to stderr as it comes; with `errors`, the
    last lines of a failing script are appended to it."""
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
    cmd = [sys.executable, str(script), r.get("url") or r["path"], *flags]
    if errors is None:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)
    else:
        p = run_teeing(cmd, errors)
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


def run_teeing(cmd: list[str], errors: list[str]) -> subprocess.CompletedProcess:
    """Run cmd with its stderr passed through line by line; on failure the last message goes to `errors`."""
    tail: list[str] = []
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as proc:
        for line in proc.stderr:
            sys.stderr.write(line)
            tail = (tail + [line.rstrip()])[-8:]
        out = proc.stdout.read()
    if proc.returncode != 0:
        errors.append(error_of(tail))
    return subprocess.CompletedProcess(cmd, proc.returncode, out, "")


def error_of(tail: list[str]) -> str:
    """The error message from the end of a failing script's stderr (run_main prints `error: …`)."""
    for i in range(len(tail) - 1, -1, -1):
        if tail[i].startswith("error:"):
            return "\n".join(tail[i:]).removeprefix("error:").strip()
    return "\n".join(line for line in tail if line.strip())[-500:] or "failed"


@lru_cache(maxsize=None)
def known_flags(script: Path) -> frozenset[str]:
    """The option strings a source script's argparse knows (from its --help)."""
    p = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True)
    return frozenset(re.findall(r"(?<![\w-])(--?[A-Za-z][\w-]*)", p.stdout))


def flags_for(script: Path, flags: list[str]) -> list[str]:
    """The flags (with their values) this script knows; the others are for other inputs' sources."""
    known, out, i = known_flags(script), [], 0
    while i < len(flags):
        flag = flags[i]
        value = [flags[i + 1]] if i + 1 < len(flags) and not flags[i + 1].startswith("-") else []
        if flag.split("=", 1)[0] in known:
            out += [flag] + value
        i += 1 + len(value)
    return out


def script_of(text: str, sources_dir: Path = SOURCES_DIR) -> Path:
    r = route(text)
    script = sources_dir / r["source"] / "prepare.py"
    return script if script.is_file() else sources_dir / "video" / "prepare.py"


def prepare_many(inputs: list[str], flags: list[str], sources_dir: Path = SOURCES_DIR,
                 root: Path | None = None) -> tuple[int, dict]:
    """(exit code, {kind: inputs, items, digest_dir})."""
    items, codes = [], []
    for n, text in enumerate(inputs, 1):
        log(f"input {n}/{len(inputs)}: {text}")
        errors: list[str] = []
        try:
            code, env = dispatch(text, flags_for(script_of(text, sources_dir), flags), sources_dir, errors)
        except SkillError as e:
            code, env, errors = 1, None, [str(e)]
        codes.append(code)
        items.append(env if env is not None else {"input": text, "error": errors[-1] if errors else "failed",
                                                  "exit_code": code})
    ok = [i for i in items if "error" not in i]
    folder = None
    if len(ok) >= 2:
        folder = digest_dir([{k: i.get(k) for k in ("source", "kind", "title", "url", "dir", "summary_exists")}
                             for i in ok], date.today().isoformat(), root)
    code = 0 if ok else max(codes)
    return code, {"kind": "inputs", "items": items, "digest_dir": str(folder) if folder else None,
                  "template": str(SOURCES_DIR.parent / "templates" / "shared" / "digest.md") if folder else None}


def warn_legacy() -> None:
    """Point at the migration when the video library still has folders from before the multi-source layout."""
    videos = source_root("video")
    n = sum(1 for m in videos.rglob("metadata.json") if is_legacy(read_json(m))) if videos.is_dir() else 0
    if n:
        log(f"{n} video folder(s) use the old layout: run {SOURCES_DIR / 'video' / 'migrate_library.py'} --apply "
            "(tell the user; it renames transcript.md to content.md and re-renders the pages)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="+", help="URL or local file path (several: a digest across them)")
    raw = sys.argv[1:] if argv is None else argv
    if raw and raw[0].startswith("-") and raw[0] not in ("-h", "--help"):
        ap.error(f"put the URL or path first, then the source flags (got {raw[0]!r} first)")
    if "-h" in raw or "--help" in raw:
        ap.parse_args(["--help"])
    first_flag = next((i for i, a in enumerate(raw) if a.startswith("-")), len(raw))
    inputs, flags = raw[:first_flag], raw[first_flag:]
    warn_legacy()
    if len(inputs) > 1:
        code, out = prepare_many(inputs, flags)
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return code
    code, env = dispatch(inputs[0], flags)
    if env is not None:
        print(json.dumps(env, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    run_main(main)

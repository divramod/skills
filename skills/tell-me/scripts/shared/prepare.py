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
import threading
from datetime import date
from functools import lru_cache
from pathlib import Path

from _common import ENVELOPE_KEYS, SkillError, digest_dir, is_legacy, log, read_json, run_main, source_root
from route import route

SOURCES_DIR = Path(__file__).resolve().parent.parent  # scripts/
LIST_KINDS = ("playlist", "channel")


def dispatch(text: str, flags: list[str], sources_dir: Path = SOURCES_DIR,
             errors: list[str] | None = None) -> tuple[int, dict | None]:
    """(exit code, envelope). The source script's progress goes to stderr as it comes; the error message of a
    failing script is appended to `errors`. A usage error of the script (argparse exits 2, like a missing tool)
    becomes exit 1."""
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
    p = run_teeing([sys.executable, str(script), r.get("url") or r["path"], *flags],
                   errors if errors is not None else [])
    if p.returncode != 0:
        return (1 if p.returncode == 2 and p.stderr == "usage" else p.returncode), None
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
    """Run cmd with its stderr passed through line by line while stdout is collected in a thread (a big envelope
    must not fill the pipe). On failure its error message goes to `errors`; the result's stderr is "usage" for
    an argparse usage error."""
    tail: list[str] = []
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as proc:
        out: list[str] = []
        reader = threading.Thread(target=lambda: out.append(proc.stdout.read()), daemon=True)
        reader.start()
        for line in proc.stderr:
            sys.stderr.write(line)
            tail = (tail + [line.rstrip()])[-8:]
        reader.join()
    usage = any(": error: " in line for line in tail)
    if proc.returncode != 0:
        errors.append(error_of(tail))
    return subprocess.CompletedProcess(cmd, proc.returncode, "".join(out), "usage" if usage else "")


def error_of(tail: list[str]) -> str:
    """A failing script's error message: argparse's text after `: error: `, else its last message (run_main
    logs it as `[tell-me] <message>`)."""
    lines = [line for line in tail if line.strip()]
    for line in reversed(lines):
        if ": error: " in line:
            return line.split(": error: ", 1)[1].strip()
    return lines[-1].removeprefix("[tell-me] ").strip() if lines else "failed"


_OPTION_RE = re.compile(r"\[(--?[A-Za-z][\w-]*)( [^\]\s]+)?\]")


@lru_cache(maxsize=None)
def known_flags(script: Path) -> dict[str, bool]:
    """{option: takes a value} for a source script, from the usage block of its --help (`[--lang LANG]`)."""
    p = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True)
    usage = p.stdout.split("\n\n", 1)[0]
    return {flag: bool(value) for flag, value in _OPTION_RE.findall(usage) if flag not in ("-h", "--help")}


def split_flags(flags: list[str], known: dict[str, bool]) -> list[tuple[str, list[str]]]:
    """[(flag, its value tokens)] for the flags after the inputs; SkillError for a token that is neither a flag
    nor the value of one (an input after the flags) and for a flag no source knows."""
    out, i = [], 0
    while i < len(flags):
        token = flags[i]
        if not token.startswith("-"):
            raise SkillError(f"{token!r} after the flags: put every URL or path first, then the flags "
                             f"(a path starting with '-': ./{token})")
        name = token.split("=", 1)[0]
        if name not in known:
            raise SkillError(f"{name} is a flag none of these inputs' sources knows")
        value = [flags[i + 1]] if known[name] and "=" not in token and i + 1 < len(flags) else []
        out.append((token, value))
        i += 1 + len(value)
    return out


def flags_for(script: Path, flags: list[tuple[str, list[str]]]) -> list[str]:
    """The flags (with their values) this script knows; the others are for other inputs' sources."""
    known = known_flags(script)
    return [t for flag, value in flags if flag.split("=", 1)[0] in known for t in (flag, *value)]


def script_of(text: str, sources_dir: Path = SOURCES_DIR) -> Path:
    r = route(text)
    script = sources_dir / r["source"] / "prepare.py"
    return script if script.is_file() else sources_dir / "video" / "prepare.py"


def prepare_many(inputs: list[str], flags: list[str], sources_dir: Path = SOURCES_DIR,
                 root: Path | None = None) -> tuple[int, dict]:
    """(exit code, {kind: inputs, items, digest_dir, digest_exists, template}). The same input twice is
    prepared once."""
    inputs = list(dict.fromkeys(inputs))
    scripts = {}
    for text in inputs:
        try:
            scripts[text] = script_of(text, sources_dir)
        except SkillError:
            scripts[text] = None  # dispatch reports it
    known: dict[str, bool] = {}
    for script in {s for s in scripts.values() if s}:
        known |= known_flags(script)
    parsed = split_flags(flags, known)
    items, codes, dirs = [], [], set()
    for n, text in enumerate(inputs, 1):
        log(f"input {n}/{len(inputs)}: {text}")
        errors: list[str] = []
        try:
            script = scripts[text]
            code, env = dispatch(text, flags_for(script, parsed) if script else [], sources_dir, errors)
        except SkillError as e:
            code, env, errors = 1, None, [str(e)]
        codes.append(code)
        if env is not None and env.get("dir") in dirs:
            log(f"{text} is the same item as an earlier input: listed once")
            continue
        if env is not None:
            dirs.add(env.get("dir"))
        items.append(env if env is not None else {"input": text, "error": errors[-1] if errors else "failed",
                                                  "exit_code": code})
    ok = [i for i in items if "error" not in i]
    folder = None
    if len(ok) >= 2:
        folder = digest_dir([{k: i.get(k) for k in ("source", "kind", "title", "url", "dir", "summary_exists")}
                             for i in ok], date.today().isoformat(), root)
    code = 0 if ok else max(codes)
    return code, {"kind": "inputs", "items": items, "digest_dir": str(folder) if folder else None,
                  "digest_exists": (folder / "digest.md").exists() if folder else None,
                  "template": str(SOURCES_DIR.parent / "templates" / "shared" / "digest.md") if folder else None}


def warn_legacy() -> None:
    """Point at the migration when the video library still has folders from before the multi-source layout."""
    videos = source_root("video")
    n = sum(1 for m in videos.rglob("metadata.json") if is_legacy(read_json(m))) if videos.is_dir() else 0
    if n:
        log(f"{n} video folder(s) use the old layout: run {SOURCES_DIR / 'video' / 'migrate_library.py'} --apply "
            "(tell the user; it renames each old transcript file to content.md and re-renders the pages)")


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
    if not inputs:
        ap.error("give at least one URL or path")
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

#!/usr/bin/env python3
"""Prepare any input for summarizing: route it to its source, run scripts/<source>/prepare.py.

route.py picks the source (video, web, github, x, hn, file); the source script fetches the content
into its library folder (content file with anchor links + metadata.json) and prints the envelope.
This script checks the envelope and prints it unchanged, so the agent reads `subskill` and
`template` next. Every flag after the input goes to the source script (e.g. --skip-download,
--visual, --lang for video). Exit codes pass through: 1 expected error, 2 missing tool (the
message names the source's install-prerequisites.sh).

Usage: prepare.py "<url-or-path>" [source flags]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from _common import ENVELOPE_KEYS, SkillError, log, run_main
from route import route

SOURCES_DIR = Path(__file__).resolve().parent.parent  # scripts/
LIST_KINDS = ("playlist", "channel")


def dispatch(text: str, flags: list[str], sources_dir: Path = SOURCES_DIR) -> tuple[int, dict | None]:
    """(exit code, envelope). The source script's progress goes straight to stderr."""
    r = route(text)
    script = sources_dir / r["source"] / "prepare.py"
    if not script.is_file():
        raise SkillError(f"source '{r['source']}' not supported yet ({text})")
    log(f"source: {r['source']} ({r['kind']}) -> {script.relative_to(sources_dir)}")
    p = subprocess.run([sys.executable, str(script), r.get("url") or r["path"], *flags],
                       stdout=subprocess.PIPE, text=True)
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="URL or local file path")
    args, flags = ap.parse_known_args(argv)
    code, env = dispatch(args.input, flags)
    if env is not None:
        print(json.dumps(env, indent=2, ensure_ascii=False))
    return code


if __name__ == "__main__":
    run_main(main)

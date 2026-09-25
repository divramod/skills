#!/usr/bin/env python3
"""Check candidate similar articles against the library (no network).

The agent finds similar articles with web search; this script takes their URLs, drops the article
itself and duplicates (by canonical URL), and marks the ones that already have a summary in the
library (any source: an article may also be an HN thread or a repo there). Prints JSON:
{"articles": [{url, source, id, summary?}]}, where `summary` is the path of the summary.html
relative to <dir>, ready to link as ([summary](<path>)).

Usage: related.py "<dir>" --url <u1> --url <u2> ...
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

from _common import SkillError, find_by_id, library_root, log, read_json, run_main
from route import route


def related(folder: Path, urls: list[str], root: Path | None = None) -> list[dict]:
    root = root or library_root()
    seen = {read_json(folder / "metadata.json").get("id")}
    out = []
    for url in urls:
        try:
            r = route(url)
        except SkillError as e:
            log(f"skipped {url}: {e}")
            continue
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        item = {"url": url, "source": r["source"], "id": r["id"]}
        known = find_by_id(r["source"], r["id"], root)
        if known and (known / "summary.html").exists():
            item["summary"] = os.path.relpath(known / "summary.html", folder).replace(os.sep, "/")
        out.append(item)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir", type=Path, help="the article's library folder (the envelope's dir)")
    ap.add_argument("--url", action="append", default=[], help="a candidate article URL (repeat)")
    args = ap.parse_args(argv)
    if not (args.dir / "metadata.json").is_file():
        raise SkillError(f"{args.dir} is not a prepared library folder (no metadata.json)")
    print(json.dumps({"articles": related(args.dir, args.url)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    run_main(main)

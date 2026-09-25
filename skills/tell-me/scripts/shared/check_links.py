#!/usr/bin/env python3
"""Check every external link in a summary body and find how current each source is.

Reads markdown (stdin, --file, or a folder's summary.md), finds the http(s) links (skipping the
source's own anchor links: video timestamps, article [¶n] paragraphs and [#] headings), requests each one in parallel and prints one JSON object:
{"ok": [...], "unverified": [...], "broken": [...]}. Each entry is {url, status, final_url?, error?,
dates?}, where `dates` comes from link_dates.py (publish date, versions, last commit, ...).

--annotate writes each link's date label right after it: [Title](url) *(published 2025-06-03)*.
Re-running replaces earlier labels, so the dates can be refreshed. With stdin/--file the annotated
body goes to stdout (JSON to stderr); with --folder, summary.md is updated in place and re-rendered.

- ok:         2xx/3xx
- unverified: the site blocks scripts (401/403/405/429/503/999, typical for Amazon and Goodreads) or timed out
- broken:     404/410/other 4xx/5xx, or the host doesn't resolve. Fix or drop these links.
Exit code 1 when anything is broken.

Usage: check_links.py [--file F | --folder DIR] [--annotate] [--no-dates] < body.md
Requires: yt-dlp for YouTube dates (optional; other sources need nothing).
"""
from __future__ import annotations

import argparse
import json
import re
import socket
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from _common import run_main
from link_dates import date_info, youtube_dates, youtube_id

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
BLOCKED = {401, 403, 405, 429, 503, 999}
# Markdown link targets may hold one level of balanced parentheses: wiki/Fine-tuning_(deep_learning)
_LINK_RE = re.compile(r"\]\((https?://(?:[^()\s]|\([^()\s]*\))+)\)|<(https?://[^>\s]+)>|(?<![(<\[])(https?://[^\s)\]>]+[^\s)\]>.,;:!?])")
_VIDEO_LINK_RE = re.compile(r"[?&#]t=\d+s?$|:~:text=")
# Anchor links into the source itself (copied from its content file): [¶3](url#:~:text=...), [#](url#heading).
_ANCHOR_LINK_RE = re.compile(r"\[(?:¶\d+|#)\]\([^)\s]*\)")


def extract_links(text: str) -> list[str]:
    """External links in document order, deduplicated; the source's own anchor links (video timestamps,
    article paragraphs and headings) are skipped."""
    seen: dict[str, None] = {}
    for m in _LINK_RE.finditer(_ANCHOR_LINK_RE.sub("", text)):
        url = next(g for g in m.groups() if g)
        if not _VIDEO_LINK_RE.search(url):
            seen.setdefault(url, None)
    return list(seen)


def classify(status: int | None, error: str | None = None) -> str:
    if status is None:
        return "unverified" if error and "timed out" in error else "broken"
    if status < 400:
        return "ok"
    return "unverified" if status in BLOCKED else "broken"


def check(url: str, timeout: float = 12) -> dict:
    """Request url (HEAD, then GET when HEAD isn't allowed) and classify the result."""
    result: dict = {"url": url}
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept-Language": "en"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                result.update(status=r.status, final_url=r.url)
        except urllib.error.HTTPError as e:
            result.update(status=e.code)
            e.close()
            if method == "HEAD" and e.code in (403, 405, 501, 503):
                continue  # some servers only refuse HEAD
        except (urllib.error.URLError, socket.timeout, TimeoutError, ValueError, OSError) as e:
            reason = getattr(e, "reason", e)
            result.update(status=None, error=str(reason))
        break
    if result.get("final_url") == url:
        result.pop("final_url")
    result["result"] = classify(result.get("status"), result.get("error"))
    return result


def _label_pattern(url: str) -> re.Pattern:
    """A markdown link to url, plus an existing date label right after it."""
    return re.compile(r"(\[(?:[^\[\]]|\[[^\]]*\])+\]\(" + re.escape(url) + r"\))(?: \*\([^)]*\)\*)?")


def annotate(text: str, labels: dict[str, str]) -> str:
    """Insert (or refresh) ` *(label)*` after every markdown link whose URL has a label."""
    for url, label in labels.items():
        text = _label_pattern(url).sub(lambda m: f"{m.group(1)} *({label})*", text)
    return text


def run_checks(text: str, dates: bool = True) -> tuple[dict[str, list], dict[str, str]]:
    """Check every link in text: ({ok, unverified, broken}, {url: date label})."""
    urls = extract_links(text)
    yt = youtube_dates([v for v in map(youtube_id, urls) if v]) if dates else {}

    def work(url: str) -> dict:
        r = check(url)
        if dates and r["result"] != "broken":
            info = date_info(r.get("final_url") or url, yt) or (date_info(url, yt) if r.get("final_url") else {})
            if info:
                r["dates"] = {k: v for k, v in info.items() if v}
        return r

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(work, urls))
    out: dict[str, list] = {"ok": [], "unverified": [], "broken": []}
    for r in results:
        out[r.pop("result")].append(r)
    labels = {r["url"]: r["dates"]["label"] for r in results if r.get("dates", {}).get("label")}
    return out, labels


def summary_line(out: dict[str, list]) -> str:
    n = sum(len(v) for v in out.values())
    dated = sum(1 for v in out.values() for r in v if r.get("dates"))
    return (f"{n} links: {len(out['ok'])} ok, {len(out['unverified'])} unverified (site blocks scripts), "
            f"{len(out['broken'])} broken; {dated} dated")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--file", type=Path, help="markdown file to check")
    src.add_argument("--folder", type=Path, help="video folder: checks its summary.md")
    ap.add_argument("--annotate", action="store_true", help="write each link's date label into the text")
    ap.add_argument("--no-dates", action="store_true", help="only check the links, don't look up dates")
    args = ap.parse_args(argv)
    if args.folder:
        text = (args.folder / "summary.md").read_text(encoding="utf-8")
    elif args.file:
        text = args.file.read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()
    out, labels = run_checks(text, dates=not args.no_dates)
    report = json.dumps(out, indent=2, ensure_ascii=False)
    if args.annotate:
        text = annotate(text, labels)
        if args.folder:
            (args.folder / "summary.md").write_text(text, encoding="utf-8")
            from render_html import write as write_html
            write_html(args.folder)
            print(report)
        else:
            print(report, file=sys.stderr)
            print(text, end="")
    else:
        print(report)
    print(f"[tell-me] {summary_line(out)}", file=sys.stderr)
    return 1 if out["broken"] else 0


if __name__ == "__main__":
    run_main(main)

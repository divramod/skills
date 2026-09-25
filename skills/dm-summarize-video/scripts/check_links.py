#!/usr/bin/env python3
"""Check every external link in a summary body before it is saved. Stdlib only.

Reads markdown (stdin, --file, or a folder's summary.md), finds the http(s) links (skipping the
video's own timestamp links), requests each one in parallel and prints one JSON object:
{"ok": [...], "unverified": [...], "broken": [...]}. Each entry is {url, status, final_url?, error?}.

- ok:         2xx/3xx
- unverified: the site blocks scripts (401/403/405/429/503/999, typical for Amazon and Goodreads) or timed out
- broken:     404/410/other 4xx/5xx, or the host doesn't resolve. Fix or drop these links.
Exit code 1 when anything is broken.

Usage: check_links.py [--file F | --folder DIR] < body.md
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

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
BLOCKED = {401, 403, 405, 429, 503, 999}
# Markdown link targets may hold one level of balanced parentheses: wiki/Fine-tuning_(deep_learning)
_LINK_RE = re.compile(r"\]\((https?://(?:[^()\s]|\([^()\s]*\))+)\)|<(https?://[^>\s]+)>|(?<![(<\[])(https?://[^\s)\]>]+[^\s)\]>.,;:!?])")
_VIDEO_LINK_RE = re.compile(r"[?&#]t=\d+s?$")


def extract_links(text: str) -> list[str]:
    """External links in document order, deduplicated; the video's own timestamp links are skipped."""
    seen: dict[str, None] = {}
    for m in _LINK_RE.finditer(text):
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--file", type=Path, help="markdown file to check")
    src.add_argument("--folder", type=Path, help="video folder: checks its summary.md")
    args = ap.parse_args(argv)
    if args.folder:
        text = (args.folder / "summary.md").read_text(encoding="utf-8")
    elif args.file:
        text = args.file.read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()
    urls = extract_links(text)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(check, urls))
    out: dict[str, list] = {"ok": [], "unverified": [], "broken": []}
    for r in results:
        out[r.pop("result")].append(r)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"[dm-summarize-video] {len(urls)} links: {len(out['ok'])} ok, {len(out['unverified'])} unverified "
          f"(site blocks scripts), {len(out['broken'])} broken", file=sys.stderr)
    return 1 if out["broken"] else 0


if __name__ == "__main__":
    run_main(main)

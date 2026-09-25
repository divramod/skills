#!/usr/bin/env python3
"""Find past Hacker News discussions of the same article.

Searches Algolia for stories whose URL is the thread's article (http/https, www and a trailing slash don't
matter), drops the thread itself, and prints JSON: {"article": <url>, "discussions": [{id, url, title, points,
comments, date, summary?}]}, the ones with the most comments first. `summary` is the path of an existing
summary.html relative to <dir>, ready to link as ([summary](<path>)). A text post (Ask HN) has no article: the
list is empty.

Usage: related.py "<dir>" [--limit N]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

from _common import SkillError, find_by_id, library_root, log, read_json, run_main
from prepare import ITEM, get_json
from route import host_of

SEARCH = "https://hn.algolia.com/api/v1/search?"


def same_page(a: str, b: str) -> bool:
    pa, pb = urllib.parse.urlsplit(a), urllib.parse.urlsplit(b)
    return host_of(a) == host_of(b) and pa.path.rstrip("/") == pb.path.rstrip("/") and pa.query == pb.query


def past_discussions(article: str, own_id: str, limit: int = 10, root: Path | None = None,
                     folder: Path | None = None) -> list[dict]:
    query = urllib.parse.urlencode({"query": article, "restrictSearchableAttributes": "url", "tags": "story",
                                    "hitsPerPage": 100})
    hits = (get_json(SEARCH + query) or {}).get("hits") or []
    out = []
    for h in hits:
        if str(h.get("objectID")) == own_id or not h.get("url") or not same_page(h["url"], article):
            continue
        item = {"id": str(h["objectID"]), "url": f"{ITEM}{h['objectID']}", "title": h.get("title"),
                "points": h.get("points"), "comments": h.get("num_comments") or 0,
                "date": (h.get("created_at") or "")[:10] or None}
        known = find_by_id("hn", item["id"], root)
        if known and (known / "summary.html").exists() and folder:
            item["summary"] = os.path.relpath(known / "summary.html", folder).replace(os.sep, "/")
        out.append(item)
    out.sort(key=lambda d: (-d["comments"], -(d["points"] or 0)))
    return out[:limit]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir", type=Path, help="the thread's library folder (the envelope's dir)")
    ap.add_argument("--limit", type=int, default=10, help="at most this many discussions (default 10)")
    args = ap.parse_args(argv)
    meta = read_json(args.dir / "metadata.json")
    if meta.get("source") != "hn":
        raise SkillError(f"{args.dir} is not a prepared Hacker News thread (no hn metadata.json)")
    article = (meta.get("extras") or {}).get("article_url")
    found = past_discussions(article, str(meta.get("id")), args.limit, library_root(), args.dir) if article else []
    log(f"{len(found)} past discussions of {article}" if article else "a text post: no article to search for")
    print(json.dumps({"article": article, "discussions": found}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    run_main(main)

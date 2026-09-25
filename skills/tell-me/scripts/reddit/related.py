#!/usr/bin/env python3
"""Find other Reddit posts of the same article (other subreddits, earlier submissions).

Searches the Arctic Shift archive for posts whose URL is the post's article (http/https, www and a trailing slash
don't matter), drops the post itself, and prints JSON: {"article": <url>, "discussions": [{id, url, title,
subreddit, score, comments, date, summary?}]}, the ones with the most comments first. `summary` is the path of an
existing summary.html relative to <dir>, ready to link as ([summary](<path>)). A text post has no article: the list
is empty.

Usage: related.py "<dir>" [--limit N]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

from _common import SkillError, find_by_id, library_root, log, read_json, run_main
from prepare import REDDIT, arctic
from route import host_of

FIELDS = "id,subreddit,title,score,num_comments,created_utc,url"


def same_page(a: str, b: str) -> bool:
    pa, pb = urllib.parse.urlsplit(a), urllib.parse.urlsplit(b)
    return host_of(a) == host_of(b) and pa.path.rstrip("/") == pb.path.rstrip("/") and pa.query == pb.query


def other_posts(article: str, own_id: str, limit: int = 10, root: Path | None = None,
                folder: Path | None = None) -> list[dict]:
    query = urllib.parse.urlencode({"url": article, "limit": 100, "fields": FIELDS})
    out = []
    for p in (arctic(f"posts/search?{query}") or {}).get("data") or []:
        if str(p.get("id")) == own_id or not p.get("url") or not same_page(p["url"], article):
            continue
        sub = p.get("subreddit") or "unknown"
        item = {"id": str(p["id"]), "url": f"{REDDIT}/r/{sub}/comments/{p['id']}/", "title": p.get("title"),
                "subreddit": sub, "score": p.get("score"), "comments": p.get("num_comments") or 0,
                "date": datetime.fromtimestamp(float(p["created_utc"]), timezone.utc).strftime("%Y-%m-%d")
                if p.get("created_utc") else None}
        known = find_by_id("reddit", item["id"], root)
        if known and (known / "summary.html").exists() and folder:
            item["summary"] = os.path.relpath(known / "summary.html", folder).replace(os.sep, "/")
        out.append(item)
    out.sort(key=lambda d: (-d["comments"], -(d["score"] or 0)))
    return out[:limit]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir", type=Path, help="the post's library folder (the envelope's dir)")
    ap.add_argument("--limit", type=int, default=10, help="at most this many posts (default 10)")
    args = ap.parse_args(argv)
    meta = read_json(args.dir / "metadata.json")
    if meta.get("source") != "reddit":
        raise SkillError(f"{args.dir} is not a prepared Reddit post (no reddit metadata.json)")
    article = (meta.get("extras") or {}).get("article_url")
    found = other_posts(article, str(meta.get("id")), args.limit, library_root(), args.dir) if article else []
    log(f"{len(found)} other Reddit posts of {article}" if article else "a text post: no article to search for")
    print(json.dumps({"article": article, "discussions": found}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    run_main(main)

#!/usr/bin/env python3
"""Find repositories similar to a prepared GitHub repo (or the repo of a prepared issue / pull request).

Searches GitHub for the repo's topics (each of the first six, most stars first) and, with --query, for the
agent's own keywords; ranks the hits by the topics they share with the repo, a rare topic (`readability`)
counting more than a common one (`cli`, from each search's total), then stars; drops the repo itself and forks;
marks the ones that already have a summary in the library. Prints JSON: {"repo": <o/r>, "topics": [...],
"similar": [{repo, url, description, stars, pushed, shared_topics, score, archived?, summary?}]}. `summary` is the path of
the summary.html relative to <dir>, ready to link as ([summary](<path>)).

Usage: related.py "<dir>" [--query "words"] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.parse
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

from _common import SkillError, find_by_id, library_root, log, read_json, run_main
from client import GitHub

TOPICS = 6  # topics searched one by one (the repo's own name as a topic is skipped)
REPOS = 10_000_000  # roughly the public repos with topics, for a topic's weight
PER_SEARCH = 20


def search(gh: GitHub, q: str) -> tuple[list[dict], int]:
    """(the hits, how many repos match in all)."""
    query = urllib.parse.urlencode({"q": q, "sort": "stars", "order": "desc", "per_page": PER_SEARCH})
    answer = gh.get(f"search/repositories?{query}") or {}
    return answer.get("items") or [], answer.get("total_count") or 0


def similar(gh: GitHub, repo: str, topics: list[str], query: str | None = None, limit: int = 10,
            root: Path | None = None, folder: Path | None = None) -> list[dict]:
    hits: dict[str, dict] = {}
    weight: dict[str, float] = {}  # topic -> how telling a shared one is
    name = repo.split("/")[-1].lower()
    searched = [t for t in topics if t.lower() != name][:TOPICS]
    for q in [f"topic:{t}" for t in searched] + ([query] if query else []):
        try:
            found, total = search(gh, q)
        except SkillError as e:
            log(f"search {q!r} failed: {e}")
            continue
        if q.startswith("topic:"):
            weight[q[6:]] = max(0.1, math.log10(REPOS / max(total, 1)))
        for h in found:
            hits.setdefault(h["full_name"], h)
    mine = set(searched)
    out = []
    for full, h in hits.items():
        if full.lower() == repo.lower() or h.get("fork"):
            continue
        shared = sorted(mine & set(h.get("topics") or []))
        item = {"repo": full, "url": h.get("html_url"), "description": h.get("description"),
                "stars": h.get("stargazers_count") or 0, "pushed": (h.get("pushed_at") or "")[:10] or None,
                "shared_topics": shared, "score": round(sum(weight.get(t, 1.0) for t in shared), 2)}
        if h.get("archived"):
            item["archived"] = True
        known = find_by_id("github", full, root)
        if known and (known / "summary.html").exists() and folder:
            item["summary"] = os.path.relpath(known / "summary.html", folder).replace(os.sep, "/")
        out.append(item)
    out.sort(key=lambda d: (-d["score"], -d["stars"]))
    return out[:limit]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir", type=Path, help="the repo's (or thread's) library folder (the envelope's dir)")
    ap.add_argument("--query", help="own search keywords, e.g. 'html to markdown extractor'")
    ap.add_argument("--limit", type=int, default=10, help="at most this many repos (default 10)")
    args = ap.parse_args(argv)
    meta = read_json(args.dir / "metadata.json")
    if meta.get("source") != "github":
        raise SkillError(f"{args.dir} is not a prepared GitHub item (no github metadata.json)")
    repo = str(meta["id"]).split("#")[0]
    gh = GitHub()
    topics = (meta.get("extras") or {}).get("topics")
    if topics is None and "#" in str(meta["id"]):  # an issue / pull request: the repo's topics
        topics = gh.get(f"repos/{repo}").get("topics")
    topics = topics or []
    if not topics and not args.query:
        raise SkillError(f"{repo} has no topics: pass --query with a few words on what it does")
    found = similar(gh, repo, topics, args.query, args.limit, library_root(), args.dir)
    log(f"{len(found)} similar repos ({gh.mode})")
    print(json.dumps({"repo": repo, "topics": topics, "similar": found}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    run_main(main)

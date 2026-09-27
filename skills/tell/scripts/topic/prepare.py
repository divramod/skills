#!/usr/bin/env python3
"""Prepare a topic: search every kind of source for it and list the candidates in the topic's folder.

A topic has no content of its own: like a playlist, it lists items. search.py runs each search (the topic and
every --also query, in parallel), plus the summarized library items that name the topic (first, `found:
library`), are merged by source and id (a repo found by the web search and by
GitHub's is listed once, under github), each capped at --limit, and a candidate that is already summarized gets
`summary_exists` and its `dir`. Written to <root>/topics/<topic>/: candidates.json, candidates.md (the same as a
list: the page's content section) and metadata.json (kind:
digest, so the digest across the chosen items lands in the same folder via shared/prepare.py --digest-dir).

Prints the envelope: {source: topic, kind: topic, dir, title, queries, candidates: {video, web, github, x, hn,
reddit, file}, counts, notes, digest_exists, subskill, template}. `notes` names each search that failed or
could not run (X: always, it has no search without a login).

Usage: prepare.py "<topic>" [--also "<query>" ...] [--limit N] [--only video,web,github,hn,file] [--dir DIR ...]
Requires: yt-dlp (video search). Optional: gh (GitHub search: 30 a minute instead of 10), rg (local search without
Spotlight).
"""
from __future__ import annotations

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from itertools import zip_longest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

import search  # noqa: E402
from _common import (KIND_DIRS, MissingTool, SkillError, contract, dir_for, install_script, library_root, log,  # noqa: E402
                     read_json, require, run_main, subskill_path, template_path, update_json, write_json)

BUCKETS = ("video", "web", "github", "x", "hn", "reddit", "file")  # candidates by tell source
LABELS = {"video": "Videos", "web": "Articles and pages", "github": "GitHub repos", "x": "X posts",
          "hn": "Hacker News threads", "reddit": "Reddit threads", "file": "Local documents"}
X_NOTE = ("x: X has no search without a login: web-search `site:x.com <topic>` yourself and add the post links "
          "(…/status/<id>) you choose")


def library_index(root: Path) -> dict[tuple[str, str], Path]:
    """(source, id) -> folder of every summarized item in the library."""
    out = {}
    for source in {s for s in KIND_DIRS if s != "topic"}:
        base = root / KIND_DIRS[source]
        if not base.is_dir():
            continue
        for meta_path in base.rglob("metadata.json"):
            meta = read_json(meta_path)
            c = contract(meta)
            if meta.get("kind") != "digest" and c["id"] and (meta_path.parent / "summary.md").exists():
                out[(c["source"], str(c["id"]))] = meta_path.parent
    return out


def library_matches(root: Path, queries: list[str], index: dict[tuple[str, str], Path]) -> list[dict]:
    """Summarized library items whose title or summary names the topic (as a whole word), as candidates."""
    words = [re.compile(rf"(?<!\w){re.escape(q)}(?!\w)", re.I) for q in queries]
    out = []
    for (source, _), folder in index.items():
        meta = read_json(folder / "metadata.json")
        c = contract(meta)
        text = f"{c['title']}\n{(folder / 'summary.md').read_text(encoding='utf-8', errors='replace')}"
        hit = next((q for q, w in zip(queries, words) if w.search(text)), None)
        where = (c["extras"] or {}).get("original_path") or c["url"]
        if hit and where and (found := search.candidate(where, c["title"], hit, author=c["author"],
                                                       date=c["published"], found="library")):
            out.append(found)
    return out


def merge(results: list[list[dict]], limit: int, known: dict[tuple[str, str], Path]) -> dict[str, list[dict]]:
    """Candidates by source, each once, at most `limit` per source; library items marked. The searches take
    turns (every search's first result, then every second one, ...), so each query gets its share of a kind; an
    item found twice keeps the fields of the earlier search."""
    buckets: dict[str, list[dict]] = {b: [] for b in BUCKETS}
    seen = set()
    for rank in zip_longest(*results):
        for c in filter(None, rank):
            key = (c["source"], str(c["id"]))
            if key in seen or c["source"] not in buckets:
                continue
            seen.add(key)
            folder = known.get(key)
            c = c | {"summary_exists": bool(folder)} | ({"dir": str(folder)} if folder else {})
            buckets[c["source"]].append(c)
    return {b: items[:limit] for b, items in buckets.items()}


def run_searches(queries: list[str], kinds: list[str], limit: int, dirs: list[Path] | None,
                 notes: list[str]) -> list[list[dict]]:
    """Every (kind, query) search in parallel; results in kind order (web last), then query order. A failed search goes to
    `notes`; a missing optional tool too (rg), a missing yt-dlp stops with exit 2."""
    # the web search last: a repo or thread it finds keeps the fields of its own search (stars, comments)
    jobs = [(k, q) for k in sorted(kinds, key=lambda k: k == "web") for q in queries]

    def one(job):
        kind, query = job
        try:
            return search.run(kind, query, limit, dirs)
        except MissingTool as e:
            if kind == "video":
                raise
            notes.append(f"{kind}: {str(e).splitlines()[0]} ({install_script(__file__)})")
        except SkillError as e:
            notes.append(f"{kind} ({query}): {e}")
        return []

    with ThreadPoolExecutor(max_workers=6) as pool:
        return list(pool.map(one, jobs))


def candidates_md(topic: str, queries: list[str], day: str, candidates: dict[str, list[dict]],
                  notes: list[str]) -> str:
    """The search results as a readable list: the topic page's content section."""
    lines = [f"# {topic}", "", f"Searched {day} for: {' · '.join(queries)}", ""]
    for bucket, items in candidates.items():
        if not items:
            continue
        lines += [f"## {LABELS[bucket]} ({len(items)})", ""]
        for c in items:
            link = f"[{c['title']}]({c['input']})" if c["input"].startswith("http") else \
                f"[{c['title']}]({Path(c['input']).as_uri()})"
            facts = [c.get("author"), c.get("folder"), c.get("duration"), c.get("date"),
                     f"★ {c['stars']}" if c.get("stars") is not None else None,
                     f"{c['comments']} comments" if c.get("comments") is not None else None,
                     "summarized" if c.get("summary_exists") else None]
            line = f"- {link}" + "".join(f" · {f}" for f in facts if f not in (None, ""))
            lines.append(line + (f": {c['snippet']}" if c.get("snippet") else ""))
        lines.append("")
    if notes:
        lines += ["## Notes", ""] + [f"- {n}" for n in notes] + [""]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("topic")
    ap.add_argument("--also", action="append", default=[],
                    help="another query for the same topic (what an abbreviation stands for, another name)")
    ap.add_argument("--limit", type=int, default=8, help="at most this many candidates per kind (default 8)")
    ap.add_argument("--only", help=f"search only these kinds, comma-separated ({','.join(search.KINDS)})")
    ap.add_argument("--dir", type=Path, action="append",
                    help="local folder to search (repeat; default: $TELL_TOPIC_DIRS, folders split by ':', or ~)")
    args = ap.parse_args(argv)
    topic = " ".join(args.topic.removeprefix("topic:").split())
    kinds = [k.strip() for k in args.only.split(",")] if args.only else list(search.KINDS)
    if bad := [k for k in kinds if k not in search.KINDS]:
        raise SkillError(f"--only: unknown kind(s) {', '.join(bad)} (known: {', '.join(search.KINDS)})")
    if "video" in kinds:
        require("yt-dlp")
    queries = list(dict.fromkeys([topic] + [" ".join(q.split()) for q in args.also if q.strip()]))
    root = library_root()
    folder = dir_for({"source": "topic", "title": topic}, root)
    folder.mkdir(parents=True, exist_ok=True)
    log(f"searching {', '.join(kinds)} for {' / '.join(queries)}")
    notes: list[str] = []
    index = library_index(root)
    results = [library_matches(root, queries, index)] + run_searches(queries, kinds, args.limit, args.dir, notes)
    candidates = merge(results, args.limit, index)
    if not candidates["x"]:
        notes.append(X_NOTE)
    counts = {b: len(items) for b, items in candidates.items() if items}
    log(f"{sum(counts.values())} candidates: " + (", ".join(f"{n} {b}" for b, n in counts.items()) or "none"))
    today = date.today().isoformat()
    write_json(folder / "candidates.json", {"topic": topic, "queries": queries, "searched": today,
                                            "candidates": candidates, "notes": notes})
    (folder / "candidates.md").write_text(candidates_md(topic, queries, today, candidates, notes), encoding="utf-8")
    meta = read_json(folder / "metadata.json")
    update_json(folder / "metadata.json", {
        "source": "topic", "kind": "digest", "id": folder.name, "title": meta.get("title") or topic,
        "queries": queries, "fetched": datetime.now().isoformat(timespec="seconds"),
        "content_file": "candidates.md", "items": meta.get("items") or []})
    digest = folder / "digest.md"
    print(json.dumps({
        "source": "topic", "kind": "topic", "dir": str(folder), "id": folder.name, "title": topic, "url": None,
        "queries": queries, "content_file": str(folder / "candidates.md"), "summary": str(digest),
        "summary_exists": digest.exists(), "digest_exists": digest.exists(),
        "subskill": str(subskill_path("topic")), "template": str(template_path("topic")),
        "counts": counts, "notes": notes, "candidates": candidates}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    run_main(main)

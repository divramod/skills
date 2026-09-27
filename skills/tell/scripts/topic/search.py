#!/usr/bin/env python3
"""Search every kind of source tell reads for a topic, without judging relevance (the agent does that).

  video   YouTube search via yt-dlp (`ytsearchN:`)
  web     Bing's RSS results (no key): blog posts, articles, docs; a result that is a repo, a video, an X post,
          an HN or a Reddit thread goes to that kind instead
  github  GitHub's repository search (gh when logged in, else the REST API)
  hn      Hacker News stories via Algolia
  x       only what the web search finds: X has no search without a login (the subskill says what to do)
  file    local documents: Spotlight (mdfind) on macOS, else ripgrep over the text formats

Every result is a candidate {input, title, source, kind, ...}: `input` is what shared/prepare.py takes (a URL or
a path). A search that fails is reported, the others go on.

Usage: search.py "<query>" [--kind video|web|github|hn|file] [--limit N] [--dir DIR ...]   (prints JSON)
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

from _common import BOT_HINT, SkillError, browser_cookies, fmt_ts, is_bot_error, library_root, log, require, \
    run_main, ytdlp_base
from route import route

TIMEOUT = 30
BING = "https://www.bing.com/search?"
ALGOLIA = "https://hn.algolia.com/api/v1/search?"
HN_ITEM = "https://news.ycombinator.com/item?id="
KINDS = ("video", "web", "github", "hn", "file")
# Local documents worth summarizing (route.DOC_EXT without data files and saved web pages).
FILE_EXT = {".pdf", ".docx", ".doc", ".pptx", ".xlsx", ".epub", ".odt", ".rtf", ".md", ".txt", ".ipynb", ".tex",
            ".rst", ".org"}
TEXT_EXT = {".md", ".txt", ".ipynb", ".tex", ".rst", ".org"}  # what ripgrep (and the snippet) can read
SKIP_DIRS = {"node_modules", "site-packages", "__pycache__", "venv", "Library", "Applications"}


def phrase(query: str) -> str:
    """A query of several words as one phrase for the search engines ("open knowledge format")."""
    return f'"{query}"' if " " in query.strip() and '"' not in query else query


def get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (tell)"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raise SkillError(f"{urllib.parse.urlsplit(url).hostname} answered HTTP {e.code}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise SkillError(f"could not reach {urllib.parse.urlsplit(url).hostname}: {getattr(e, 'reason', e)}")


def clean(text: str | None, limit: int = 240) -> str | None:
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()
    return (text[:limit].rsplit(" ", 1)[0] + " …" if len(text) > limit else text) or None


def candidate(input_: str, title: str | None, query: str, **fields) -> dict | None:
    """A candidate with its tell source and kind (route.py), or None when tell can't read it."""
    try:
        r = route(input_)
    except SkillError:
        return None
    if r["source"] == "topic":
        return None
    out = {"input": r.get("url") or r.get("path") or input_, "title": clean(title, 160) or input_,
           "source": r["source"], "kind": r["kind"], "id": r["id"], "query": query}
    return out | {k: v for k, v in fields.items() if v not in (None, "", [])}


# ---------------------------------------------------------------- searches


def video(query: str, limit: int, cookies: str | None = None) -> list[dict]:
    require("yt-dlp")
    p = subprocess.run(ytdlp_base(cookies) + ["--flat-playlist", "-J", f"ytsearch{limit}:{query}"],
                       capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        err = p.stderr.strip()
        raise SkillError(f"YouTube search failed: {err[-200:]}" + (f"\n{BOT_HINT}" if is_bot_error(err) else ""))
    return parse_videos(json.loads(p.stdout or "{}"), query)


def parse_videos(data: dict, query: str) -> list[dict]:
    out = []
    for e in data.get("entries") or []:
        if not e.get("id") or e.get("live_status") in ("is_live", "is_upcoming") or "/shorts/" in (e.get("url") or ""):
            continue
        c = candidate(f"https://www.youtube.com/watch?v={e['id']}", e.get("title"), query,
                      author=e.get("channel") or e.get("uploader"),
                      duration=fmt_ts(e["duration"]) if e.get("duration") else None, views=e.get("view_count"),
                      snippet=clean(e.get("description")))
        if c:
            out.append(c)
    return out


def web(query: str, limit: int) -> list[dict]:
    return parse_bing(get(BING + urllib.parse.urlencode({"q": phrase(query), "format": "rss"})), query)[:limit]


def parse_bing(rss: str, query: str) -> list[dict]:
    """Bing's RSS results (its pubDate is the crawl date, not the page's: left out)."""
    try:
        root = ET.fromstring(rss)
    except ET.ParseError:
        raise SkillError("Bing did not answer RSS (a bot check?)")
    out = []
    for item in root.iter("item"):
        c = candidate(item.findtext("link") or "", item.findtext("title"), query,
                      snippet=clean(item.findtext("description")), found="web search")
        if c:
            out.append(c)
    return out


def github(query: str, limit: int) -> list[dict]:
    spec = importlib.util.spec_from_file_location("github_client", Path(__file__).resolve().parent.parent /
                                                  "github" / "client.py")
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)
    q = urllib.parse.quote(phrase(query))
    return parse_github(client.GitHub().get(f"search/repositories?q={q}&per_page={limit}"), query)


def parse_github(data: dict, query: str) -> list[dict]:
    out = []
    for r in data.get("items") or []:
        c = candidate(r.get("html_url") or "", r.get("full_name"), query, snippet=clean(r.get("description")),
                      stars=r.get("stargazers_count"), language=r.get("language"),
                      date=(r.get("pushed_at") or "")[:10] or None, fork=r.get("fork") or None,
                      archived=r.get("archived") or None)
        if c:
            out.append(c)
    return out


def hn(query: str, limit: int) -> list[dict]:
    q = urllib.parse.urlencode({"query": phrase(query), "tags": "story", "hitsPerPage": limit})
    try:
        data = json.loads(get(ALGOLIA + q))
    except ValueError:
        raise SkillError("Algolia did not answer JSON")
    return parse_hn(data, query)


def parse_hn(data: dict, query: str) -> list[dict]:
    out = []
    for h in data.get("hits") or []:
        c = candidate(f"{HN_ITEM}{h.get('objectID')}", h.get("title"), query, author=h.get("author"),
                      points=h.get("points"), comments=h.get("num_comments") or 0,
                      date=(h.get("created_at") or "")[:10] or None, article=h.get("url"),
                      snippet=clean(h.get("story_text")))
        if c:
            out.append(c)
    return out


def files(query: str, limit: int, dirs: list[Path], exclude: list[Path] | None = None) -> list[dict]:
    """Local documents that mention the query (name or text): Spotlight on macOS, else ripgrep (text formats).
    Hidden folders, Library, node_modules and the tell library itself are left out; names that match first,
    then the most recently changed."""
    exclude = [p.resolve() for p in (exclude or [])]
    if sys.platform == "darwin" and shutil.which("mdfind"):
        found = spotlight(query, dirs)
    else:
        require("rg")
        found = ripgrep(query, dirs)
    paths = [p for p in dict.fromkeys(found) if keep_file(p, exclude)]
    words = [w.lower() for w in re.findall(r"\w+", query)]
    paths.sort(key=lambda p: (not all(w in p.name.lower() for w in words), -p.stat().st_mtime))
    out = []
    for p in paths[:limit]:
        c = candidate(str(p), p.name, query, date=date.fromtimestamp(p.stat().st_mtime).isoformat(),
                      folder=str(p.parent).replace(str(Path.home()), "~", 1), snippet=snippet(p, words))
        if c:
            out.append(c)
    return out


def spotlight(query: str, dirs: list[Path]) -> list[Path]:
    out = []
    for d in dirs:
        try:
            p = subprocess.run(["mdfind", "-onlyin", str(d), query], capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired:
            log(f"Spotlight search in {d} timed out")
            continue
        out += [Path(line) for line in p.stdout.splitlines() if line.strip()]
    return out


def ripgrep(query: str, dirs: list[Path]) -> list[Path]:
    globs = [a for ext in sorted(TEXT_EXT) for a in ("-g", f"*{ext}")] + \
        [a for d in sorted(SKIP_DIRS) for a in ("-g", f"!{d}/")]
    try:
        p = subprocess.run(["rg", "-l", "-i", "-F", "--max-filesize", "5M", *globs, "--", query, *map(str, dirs)],
                           capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        raise SkillError("ripgrep took longer than 120s: narrow the folders with --dir")
    return [Path(line) for line in p.stdout.splitlines() if line.strip()]


def keep_file(p: Path, exclude: list[Path]) -> bool:
    if p.suffix.lower() not in FILE_EXT or any(part.startswith(".") or part in SKIP_DIRS for part in p.parts[1:]):
        return False
    try:
        rp = p.resolve()
        return p.is_file() and not any(rp.is_relative_to(e) for e in exclude)
    except OSError:
        return False


def snippet(p: Path, words: list[str]) -> str | None:
    """The first line of a text file that has a query word."""
    if p.suffix.lower() not in TEXT_EXT or not words:
        return None
    try:
        with p.open(encoding="utf-8", errors="replace") as f:
            for n, line in enumerate(f):
                if n > 20000:
                    break
                if any(w in line.lower() for w in words):
                    return clean(line.strip("#-*> \t\n"), 200)
    except OSError:
        return None
    return None


def default_dirs() -> list[Path]:
    """$TELL_TOPIC_DIRS (folders split by ':'), else the home folder."""
    raw = os.environ.get("TELL_TOPIC_DIRS")
    return [Path(d).expanduser() for d in raw.split(":") if d] if raw else [Path.home()]


def run(kind: str, query: str, limit: int, dirs: list[Path] | None = None) -> list[dict]:
    if kind == "video":
        return video(query, limit, browser_cookies())
    if kind == "web":
        return web(query, limit)
    if kind == "github":
        return github(query, limit)
    if kind == "hn":
        return hn(query, limit)
    if kind == "file":
        return files(query, limit, dirs or default_dirs(), [library_root()])
    raise SkillError(f"unknown search kind {kind!r}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query")
    ap.add_argument("--kind", choices=KINDS, action="append", help="search only these (repeat); default: all")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--dir", type=Path, action="append", help="local folder to search (default: $TELL_TOPIC_DIRS or ~)")
    args = ap.parse_args(argv)
    out = {}
    for kind in args.kind or KINDS:
        try:
            out[kind] = run(kind, args.query, args.limit, args.dir)
        except SkillError as e:
            log(f"{kind}: {e}")
            out[kind] = {"error": str(e)}
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    run_main(main)

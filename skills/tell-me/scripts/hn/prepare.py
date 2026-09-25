#!/usr/bin/env python3
"""Prepare a Hacker News thread (the linked article and the discussion) for summarizing.

1. The item id (route.py) is the id: an already-prepared thread is reused (--refresh refetches, e.g. when the
   discussion has grown). A comment link prepares its whole story; `focus_comment` names the comment.
2. The comment tree comes from Algolia (hn.algolia.com/api/v1/items/<id>, one call). When Algolia fails or lags
   behind (brand-new items), the official Firebase API is walked instead (one call per comment). Top-level
   comments follow HN's ranking (the story's `kids`); deleted and dead comments are dropped, their replies kept.
3. The linked article goes through the web source's extractor (trafilatura + defuddle → Jina → Wayback) with
   its [¶n] paragraph anchors. Ask/Show HN text posts have no article: the post's own text is used. An article
   that cannot be extracted is noted, and the discussion is still prepared (--no-article skips it).
4. content.md: a header, `## Article`, then `## Discussion` with one `### Thread n` per top-level comment and
   one line per comment: `- **author** [→](<permalink>) (depth n, reply to <author>): text`.
5. metadata.json: the shared contract fields (extras: points, comments, threads, article_url, article_extractor,
   article_words, snapshot, focus_comment, api).
Folder: <root>/discussions/hn/<title>-<id>/. Prints the source envelope on stdout.

Usage: prepare.py <item url|id> [--refresh] [--no-article]
Requires: uvx (trafilatura) and npx (defuddle) for a linked article.
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import json
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.append(str(SCRIPTS / "shared"))  # _common + the shared steps
sys.path.append(str(SCRIPTS / "web"))  # the web extractor (a source may use another source; shared may not)

from _common import (MissingTool, SkillError, envelope, find_by_id, log, read_json, run_main, unique_dir,
                     update_json)
from extract import NotAPage, extract
from route import route

ALGOLIA = "https://hn.algolia.com/api/v1/items/"
FIREBASE = "https://hacker-news.firebaseio.com/v0/item/"
ITEM = "https://news.ycombinator.com/item?id="
TIMEOUT = 30
WORKERS = 16  # parallel Firebase requests


def web_prepare():
    """web/prepare.py as a module (for anchor()): its file name clashes with this one's."""
    spec = importlib.util.spec_from_file_location("web_prepare", SCRIPTS / "web" / "prepare.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------- fetch


def get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "tell-me"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SkillError(f"{url} answered HTTP {e.code}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise SkillError(f"could not fetch {url}: {getattr(e, 'reason', e)}")
    except json.JSONDecodeError:
        raise SkillError(f"{url} did not answer JSON")


def from_firebase(item: dict) -> dict:
    """A Firebase item in Algolia's shape (children filled in later)."""
    gone = item.get("deleted") or item.get("dead")
    return {"id": item.get("id"), "type": item.get("type"), "author": None if gone else item.get("by"),
            "text": None if gone else item.get("text"), "title": item.get("title"), "url": item.get("url"),
            "points": item.get("score"), "parent_id": item.get("parent"),
            "created_at_i": item.get("time"), "kids": item.get("kids") or [], "children": []}


def firebase_tree(item_id: int) -> dict:
    """The whole tree from Firebase, one request per item, level by level in parallel."""
    root = from_firebase(get_json(f"{FIREBASE}{item_id}.json") or {})
    if not root["id"]:
        raise SkillError(f"Hacker News has no item {item_id}")
    level = [root]
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        while level:
            kids = [(node, kid) for node in level for kid in node["kids"]]
            items = pool.map(lambda nk: get_json(f"{FIREBASE}{nk[1]}.json") or {}, kids)
            level = []
            for (node, _), item in zip(kids, items):
                child = from_firebase(item)
                if child["id"]:
                    node["children"].append(child)
                    level.append(child)
    return root


def fetch_tree(item_id: int, attempts: list[str]) -> tuple[dict, str]:
    """(the item's tree, the API it came from)."""
    try:
        tree = get_json(f"{ALGOLIA}{item_id}")
        if isinstance(tree, dict) and tree.get("id"):
            return tree, "algolia"
        attempts.append("algolia: no such item")
    except SkillError as e:
        attempts.append(f"algolia: failed ({e})")
    log(f"{attempts[-1]} -> walking the Firebase API (one request per comment)")
    return firebase_tree(item_id), "firebase"


def load_story(item_id: int, attempts: list[str]) -> tuple[dict, str, int | None]:
    """(the story's tree, the API, the comment id when item_id was a comment)."""
    tree, api = fetch_tree(item_id, attempts)
    if tree.get("type") in ("comment", "pollopt"):
        story_id = tree.get("story_id") or story_of(tree)
        log(f"{item_id} is a {tree['type']}: preparing its story {story_id}")
        tree, api = fetch_tree(story_id, attempts)
        return tree, api, item_id
    return tree, api, None


def story_of(item: dict) -> int:
    """Firebase has no story_id: walk the parents up."""
    parent = item.get("parent_id")
    while parent:
        up = get_json(f"{FIREBASE}{parent}.json") or {}
        if up.get("type") not in ("comment", "pollopt"):
            return up["id"]
        parent = up.get("parent")
    raise SkillError(f"could not find the story of item {item.get('id')}")


def ranking(story_id: int, api: str, tree: dict) -> list[int]:
    """HN's order of the top-level comments (Algolia returns them unranked)."""
    if api == "firebase":
        return tree.get("kids") or []
    try:
        return (get_json(f"{FIREBASE}{story_id}.json") or {}).get("kids") or []
    except SkillError as e:
        log(f"ranking unavailable ({e}): top-level comments stay in Algolia's order")
        return []


# ---------------------------------------------------------------- text


class CommentText(HTMLParser):
    """HN's comment HTML -> markdown: <p> paragraphs, <a> links (HN shortens their text, so the href is used),
    <i> emphasis, <pre><code> blocks."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.pre = False
        self.href = None

    def handle_starttag(self, tag, attrs):
        if tag == "p":
            self.out.append("\n\n")
        elif tag == "pre":
            self.pre = True
            self.out.append("\n\n```\n")
        elif tag == "i" and not self.pre:
            self.out.append("*")
        elif tag == "a":
            self.href = dict(attrs).get("href")

    def handle_endtag(self, tag):
        if tag == "pre":
            self.pre = False
            self.out.append("\n```\n\n")
        elif tag == "i" and not self.pre:
            self.out.append("*")
        elif tag == "a":
            self.href = None

    def handle_data(self, data):
        if self.href and not self.pre and re.match(r"https?://", self.href):
            self.out.append(self.href if data.rstrip(".").rstrip("…") in self.href else f"[{data}]({self.href})")
        else:
            self.out.append(data)


def comment_text(raw: str | None) -> str:
    parser = CommentText()
    parser.feed(raw or "")
    parser.close()
    text = re.sub(r"\s*\n```\n\n", "\n```\n\n", "".join(parser.out))  # HN's <pre> ends with a newline
    parts = re.split(r"(\n*```\n.*?\n```\n*)", text, flags=re.S)
    text = "".join(p if p.lstrip("\n").startswith("```") else re.sub(r"[ \t]+", " ", p) for p in parts)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def indent(text: str, prefix: str = "  ") -> str:
    """A comment's later lines, indented to stay inside its list item."""
    return "\n".join(line if i == 0 or not line else prefix + line for i, line in enumerate(text.splitlines()))


def discussion(tree: dict, ranks: list[int]) -> tuple[str, int, int]:
    """(the ## Discussion markdown, comment count, top-level thread count)."""
    order = {cid: i for i, cid in enumerate(ranks)}
    top = sorted(tree.get("children") or [], key=lambda c: (order.get(c.get("id"), len(order)),
                                                            c.get("created_at_i") or 0))
    sections, total, threads = [], 0, 0

    def walk(node: dict, depth: int, parent: str | None, lines: list[str]) -> int:
        count = 0
        author = node.get("author")
        if author and node.get("text"):  # a deleted or dead comment: dropped, its replies kept
            reply = f", reply to {parent}" if parent else ""
            lines.append(f"- **{author}** [→]({ITEM}{node['id']}) (depth {depth}{reply}): "
                         + indent(comment_text(node["text"])))
            count = 1
        for child in sorted(node.get("children") or [], key=lambda c: c.get("created_at_i") or 0):
            count += walk(child, depth + 1, author or parent, lines)
        return count

    for node in top:
        lines: list[str] = []
        n = walk(node, 0, None, lines)
        if not n:
            continue
        threads += 1
        total += n
        sections.append(f"### Thread {threads} ({n} comment{'s' if n != 1 else ''})\n\n" + "\n".join(lines))
    return "\n\n".join(sections), total, threads


# ---------------------------------------------------------------- article


def article(url: str, attempts: list[str]) -> tuple[str, dict]:
    """(the article markdown with [¶n] anchors, facts about it). A failure is written into the text."""
    try:
        page = extract(url)
    except MissingTool:
        raise
    except NotAPage as e:
        attempts.append(f"article: {e}")
        return f"*The link is not a web page: {e}*", {}
    except SkillError as e:
        attempts.append(f"article: failed ({e})")
        return f"*The article could not be extracted: {e}*", {}
    best = page.best
    web = web_prepare()
    base = page.snapshot or web.page_url(url)
    body = web.anchor(best.markdown, base, web.heading_ids(best.html) if best.html else {},
                      preamble=best.meta.get("title") or "")
    body = demote(body)
    facts = {"article_extractor": best.extractor, "article_words": best.words, "snapshot": page.snapshot,
             "article_gone": page.gone or None, "article_title": best.meta.get("title")}
    return body, facts


def demote(markdown: str, levels: int = 2) -> str:
    """The article's headings pushed below `## Article` (# -> ###), fenced code left alone."""
    out, fence = [], False
    for line in markdown.splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
        elif not fence and (m := re.match(r"(#{1,6})(\s)", line)):
            line = "#" * min(6, len(m.group(1)) + levels) + line[len(m.group(1)):]
        out.append(line)
    return "\n".join(out)


# ---------------------------------------------------------------- files


def iso(ts: int | None) -> str | None:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d") if ts else None


def render_content(meta: dict, extras: dict, article_md: str, discussion_md: str) -> str:
    rows = [f"# {meta['title']}", "", f"- url: {meta['url']}"]
    for label, value in (("article", extras.get("article_url")), ("posted by", meta.get("author")),
                         ("published", meta.get("published")), ("points", extras.get("points")),
                         ("comments", f"{extras['comments']} in {extras['threads']} threads"),
                         ("article extractor", extras.get("article_extractor")
                          and f"{extras['article_extractor']} ({extras['article_words']} words)"),
                         ("archived copy", extras.get("snapshot")),
                         ("focus comment", extras.get("focus_comment")
                          and f"{ITEM}{extras['focus_comment']}")):
        if value:
            rows.append(f"- {label}: {value}")
    rows += ["", "## Article", "", article_md or "*No article: a text post.*", "",
             "## Discussion", "", discussion_md or "*No comments yet.*", ""]
    return "\n".join(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("item", help="news.ycombinator.com/item?id=<id> or the bare id")
    ap.add_argument("--refresh", action="store_true", help="refetch the thread even if it was prepared before")
    ap.add_argument("--no-article", action="store_true", help="only the discussion, not the linked article")
    args = ap.parse_args(argv)

    r = route(f"{ITEM}{args.item}" if args.item.isdigit() else args.item)
    if r["source"] != "hn":
        raise SkillError(f"{args.item} is a {r['source']} input, not a Hacker News item")
    existing = find_by_id("hn", r["id"])
    if existing and (existing / "content.md").exists() and not args.refresh:
        log(f"reusing: {existing} (pass --refresh to refetch)")
        return print_envelope(existing, read_json(existing / "metadata.json"), reused=True)

    attempts: list[str] = []
    tree, api, focus = load_story(int(r["id"]), attempts)
    story_id = str(tree["id"])
    if focus:  # a comment link: the story may already be prepared
        existing = find_by_id("hn", story_id)
        if existing and (existing / "content.md").exists() and not args.refresh:
            log(f"reusing: {existing}, the story of comment {focus} (pass --refresh to refetch)")
            meta = update_json(existing / "metadata.json",
                               {"extras": read_json(existing / "metadata.json").get("extras", {})
                                | {"focus_comment": focus}})
            return print_envelope(existing, meta, reused=True)
    discussion_md, comments, threads = discussion(tree, ranking(int(story_id), api, tree))
    log(f"{api}: {comments} comments in {threads} threads")

    facts: dict = {}
    url = tree.get("url")
    if url and not args.no_article:
        log(f"article: {url}")
        article_md, facts = article(url, attempts)
    elif tree.get("text"):  # Ask HN / Show HN / a job post: the post itself
        article_md = f"**{tree.get('author')}** [→]({ITEM}{story_id}): " + comment_text(tree["text"])
    else:
        article_md = ""

    old = read_json(existing / "metadata.json") if existing else {}
    title = html.unescape(tree.get("title") or f"HN item {story_id}")
    extras = {k: v for k, v in ({"points": tree.get("points"), "comments": comments, "threads": threads,
                                 "article_url": url, "focus_comment": focus, "api": api,
                                 "attempts": attempts or None} | facts).items() if v is not None}
    meta = {
        "source": "hn", "id": story_id, "url": f"{ITEM}{story_id}", "title": title, "author": tree.get("author"),
        "published": iso(tree.get("created_at_i")), "fetched": datetime.now().isoformat(timespec="seconds"),
        "site": "Hacker News", "word_count": 0, "duration": None, "extractor": api, "content_file": "content.md",
        "extras": extras,
    }
    content = render_content(meta, extras | {"comments": comments, "threads": threads}, article_md, discussion_md)
    meta["word_count"] = len(content.split())
    folder = existing or unique_dir(meta)
    folder.mkdir(parents=True, exist_ok=True)
    log(f"{'refreshing' if existing else 'folder'}: {folder}")
    (folder / "content.md").write_text(content, encoding="utf-8")
    meta = update_json(folder / "metadata.json", meta | {"prepared_at": old.get("prepared_at") or meta["fetched"]})
    return print_envelope(folder, meta, reused=bool(existing))


def print_envelope(folder: Path, meta: dict, reused: bool) -> int:
    extras = meta.get("extras") or {}
    print(json.dumps(envelope(folder, meta, "thread", reused=reused, points=extras.get("points"),
                              comments=extras.get("comments"), threads=extras.get("threads"),
                              article_url=extras.get("article_url"), focus_comment=extras.get("focus_comment"),
                              snapshot=extras.get("snapshot"), attempts=extras.get("attempts")),
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    run_main(main)

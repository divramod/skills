#!/usr/bin/env python3
"""Prepare a web page (blog post, article, docs page) for summarizing.

1. route.py's canonical URL is the id: an already-prepared page is reused (--refresh refetches).
2. extract.py: trafilatura + defuddle on the fetched HTML, the better one wins; Jina Reader, then the
   Wayback Machine when the page yields under 200 words.
3. content.md: a header, the description and the article, where every paragraph, list and quote starts
   with an anchor link [¶n](<url>#:~:text=<its first words>) (a text fragment: browsers scroll to and
   highlight that text) and headings get [#](<url>#<id>) when the page gives them an id.
4. metadata.json: the shared contract fields (extras: description, language, image, attempts, snapshot).
Folder: <root>/articles/<site>/<title>/. Prints the source envelope on stdout.

Usage: prepare.py <url> [--refresh]
Requires: uvx (trafilatura), npx (defuddle).
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.parse
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

from _common import SkillError, envelope, find_by_id, fmt_date, log, read_json, run_main, unique_dir, update_json
from extract import extract
from route import TRACKING_PARAMS, is_route_fragment, route

LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
FRAGMENT_WORDS = 5  # a text fragment starts with this many words, more when that is not unique
MAX_FRAGMENT_WORDS = 12


# ---------------------------------------------------------------- anchors


def page_url(url: str) -> str:
    """The URL as given, minus tracking params (utm_*, fbclid, ...) and the fragment, unless the fragment is a
    single-page app's route (`#/page`): the base of every anchor."""
    parts = urllib.parse.urlsplit(url)
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
             if not TRACKING_PARAMS.match(k)]
    fragment = parts.fragment if is_route_fragment(parts.fragment) else ""
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query), fragment=fragment))


class HeadingIds(HTMLParser):
    """Collects {normalized heading text: id} for h1-h6 that carry an id (or contain an element with one)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids: dict[str, str] = {}
        self._level = 0
        self._id = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if re.fullmatch(r"h[1-6]", tag):
            self._level, self._id, self._text = 1, a.get("id"), []
        elif self._level:
            self._id = self._id or a.get("id") or (a.get("name") if tag == "a" else None)

    def handle_endtag(self, tag):
        if re.fullmatch(r"h[1-6]", tag) and self._level:
            if self._id:
                self.ids.setdefault(norm(" ".join(self._text)), self._id)
            self._level = 0

    def handle_data(self, data):
        if self._level:
            self._text.append(data)


def heading_ids(page_html: str) -> dict[str, str]:
    parser = HeadingIds()
    try:
        parser.feed(page_html)
    except Exception:  # broken HTML: heading anchors are a nice-to-have
        return {}
    return parser.ids


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text)).strip().lower()


def blocks(markdown: str) -> list[str]:
    """Split markdown into blocks at blank lines, keeping fenced code (which may contain blank lines) whole."""
    out, cur, fence = [], [], False
    for line in markdown.splitlines():
        if line.strip().startswith("```"):
            fence = not fence
        if not line.strip() and not fence:
            if cur:
                out.append("\n".join(cur))
                cur = []
            continue
        cur.append(line)
    if cur:
        out.append("\n".join(cur))
    return out


def fragment(words: list[str], base: str = "") -> str:
    """Text fragment for these words (dashes, commas and ampersands must be percent-encoded). After a URL that
    already has a fragment (an app route) the directive follows it: `#/page:~:text=...`."""
    return (":~:text=" if "#" in base else "#:~:text=") + urllib.parse.quote(" ".join(words), safe="").replace("-", "%2D")


def block_words(block: str) -> list[str]:
    """Words of a block as the browser shows them: list and quote markers, link targets, images, backticks
    and emphasis marks removed (the underscore in snake_case stays: the page shows it)."""
    text = re.sub(r"^\s*(?:(?:>\s*)+|(?:[-*+]|\d+[.)])\s+)", "", block, flags=re.M)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"(?<!\w)[*_]+|[*_]+(?!\w)|`", "", text)
    return html.unescape(text).split()


def lead(block: str) -> str:
    """The block's first paragraph as the page renders it: its first list item, or a quote up to its first
    empty `>` line. A text fragment cannot match across block elements (two <li>s, two <p>s)."""
    lines = block.splitlines()
    out = lines[:1]
    for line in lines[1:]:
        if LIST_ITEM_RE.match(line) or re.fullmatch(r"\s*(>\s*)+", line) or line.lstrip(" >").startswith("```"):
            break
        out.append(line)
    return "\n".join(out)


def anchor(markdown: str, url: str, ids: dict[str, str] | None = None) -> str:
    """Add [¶n](url#:~:text=...) to every paragraph/list/quote and [#](url#id) to headings with a known id."""
    base = page_url(url)
    ids = {} if "#" in base else ids or {}  # an #id would replace the app route
    parts = blocks(markdown)
    words = [block_words(lead(b)) if kind(b) == "text" else [] for b in parts]
    out, n = [], 0
    for i, block in enumerate(parts):
        k = kind(block)
        if k == "heading":
            hid = ids.get(norm(" ".join(block_words(block.lstrip("#")))))
            out.append(f"{block} [#]({base}#{hid})" if hid else block)
            continue
        if k != "text" or not words[i]:
            out.append(block)
            continue
        n += 1
        count = FRAGMENT_WORDS
        while count < min(MAX_FRAGMENT_WORDS, len(words[i])) and any(
                j != i and w[:count] == words[i][:count] for j, w in enumerate(words) if w):
            count += 1
        link = f"[¶{n}]({base}{fragment(words[i][:count], base)})"
        first, _, rest = block.partition("\n")
        m = re.match(r"^(\s*(?:[-*+]|\d+[.)]|>)\s+)", first)
        first = f"{m.group(1)}{link} {first[m.end():]}" if m else f"{link} {first}"
        out.append(first + ("\n" + rest if rest else ""))
    return "\n\n".join(out)


def kind(block: str) -> str:
    first = block.lstrip()
    if first.startswith("```") or block.startswith(("    ", "\t")):
        return "code"
    if re.match(r"#{1,6}\s", first):
        return "heading"
    if first.startswith("|") or re.fullmatch(r"(-\s*){3,}|(\*\s*){3,}|(_\s*){3,}", first.strip()):
        return "other"
    if re.fullmatch(r"!\[[^\]]*\]\([^)]*\)", first.strip()):
        return "other"
    return "text"


# ---------------------------------------------------------------- files


def render_content(meta: dict, extras: dict, body: str) -> str:
    rows = [f"# {meta['title']}", "", f"- url: {meta['url']}"]
    for label, value in (("site", meta.get("site")), ("author", meta.get("author")),
                         ("published", meta.get("published")),
                         ("extractor", f"{meta['extractor']} ({meta['word_count']} words)"),
                         ("archived copy", extras.get("snapshot"))):
        if value:
            rows.append(f"- {label}: {value}")
    if extras.get("description"):
        rows += ["", "## Description", "", extras["description"]]
    rows += ["", "## Article", "", body, ""]
    return "\n".join(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--refresh", action="store_true", help="refetch the page even if it was prepared before")
    args = ap.parse_args(argv)

    r = route(args.url)
    if r["source"] != "web":
        raise SkillError(f"{args.url} is a {r['source']} input, not a web page")
    existing = find_by_id("web", r["id"])
    if existing and (existing / "content.md").exists() and not args.refresh:
        log(f"reusing: {existing} (pass --refresh to refetch)")
        meta = read_json(existing / "metadata.json")
        return print_envelope(existing, meta, reused=True)

    url = page_url(r["url"])
    best, attempts, snapshot = extract(url)
    m = best.meta
    title = m.get("title") or urllib.parse.urlsplit(url).path.strip("/").split("/")[-1] or url
    host = urllib.parse.urlsplit(url).hostname or ""
    extras = {k: v for k, v in {"description": m.get("description"), "language": m.get("language"),
                                "image": m.get("image"), "attempts": attempts, "snapshot": snapshot}.items() if v}
    meta = {
        "source": "web", "id": r["id"], "url": url, "title": title, "author": m.get("author"),
        "published": fmt_date(m.get("published")), "fetched": datetime.now().isoformat(timespec="seconds"),
        "site": m.get("site") or re.sub(r"^www\.", "", host), "word_count": best.words, "duration": None,
        "extractor": best.extractor, "content_file": "content.md", "extras": extras,
    }
    folder = existing or unique_dir(meta)
    folder.mkdir(parents=True, exist_ok=True)
    log(f"{'refreshing' if existing else 'folder'}: {folder}")
    # text from an archived copy: the live page is gone, so the anchors open the snapshot
    body = anchor(best.markdown, snapshot or url, heading_ids(best.html) if best.html else {})
    (folder / "content.md").write_text(render_content(meta, extras, body), encoding="utf-8")
    old = read_json(folder / "metadata.json")
    meta = update_json(folder / "metadata.json", meta | {"prepared_at": old.get("prepared_at") or meta["fetched"]})
    return print_envelope(folder, meta, reused=bool(existing))


def print_envelope(folder: Path, meta: dict, reused: bool) -> int:
    extras = meta.get("extras") or {}
    print(json.dumps(envelope(folder, meta, "page", reused=reused, site=meta.get("site"),
                              words=meta.get("word_count"), extractor=meta.get("extractor"),
                              snapshot=extras.get("snapshot"), attempts=extras.get("attempts")),
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    run_main(main)

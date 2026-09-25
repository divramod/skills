#!/usr/bin/env python3
"""Prepare a web page (blog post, article, docs page) for summarizing.

1. route.py's canonical URL is the id: an already-prepared page is reused (--refresh refetches). After the
   fetch, the page's declared canonical URL and the URL after redirects are ids too (`extras.aliases`), so a
   short link or a URL variant finds the same folder.
2. extract.py: trafilatura + defuddle on the fetched HTML, the better one wins; Jina Reader, then the
   Wayback Machine when the page yields under 200 words.
3. content.md: a header, the description and the article, where every paragraph, list and quote starts
   with an anchor link [¶n](<url>#:~:text=<its first words>) (a text fragment: browsers scroll to and
   highlight that text) and headings get [#](<url>#<id>) when the page gives them an id.
4. metadata.json: the shared contract fields, `url` the canonical URL (extras: description, language, image,
   attempts, snapshot, gone, aliases).
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
from route import clean_query, clean_url, host_of, is_route_fragment, route, route_fragment

LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
FRAGMENT_WORDS = 5  # a text fragment starts with this many words, more when that is not unique
MAX_FRAGMENT_WORDS = 12


# ---------------------------------------------------------------- anchors


def page_url(url: str) -> str:
    """The URL as given, minus tracking params (utm_*, fbclid, ...) and the fragment, unless the fragment is a
    single-page app's route (`#/page`): the base of every anchor."""
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(parts._replace(query=clean_query(parts.query),
                                                  fragment=route_fragment(parts.fragment)))


class HeadingIds(HTMLParser):
    """Collects {normalized heading text: id} for h1-h6. The id comes from the heading itself, else from an element
    inside it (id, or `<a name>`), else from its permalink (`<a href="#id">`, Sphinx), else from the `<section id>`
    that the heading opens (Sphinx without permalinks)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids: dict[str, str] = {}
        self._level = 0
        self._id = self._href = self._section = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if re.fullmatch(r"h[1-6]", tag):
            self._level, self._id, self._href, self._text = 1, a.get("id"), None, []
        elif self._level:
            self._id = self._id or a.get("id") or (a.get("name") if tag == "a" else None)
            href = a.get("href") or ""
            if tag == "a" and href.startswith("#") and len(href) > 1:
                self._href = self._href or urllib.parse.unquote(href[1:])
        else:
            self._section = a.get("id") if tag == "section" else None

    def handle_endtag(self, tag):
        if re.fullmatch(r"h[1-6]", tag) and self._level:
            hid = self._id or self._href or self._section
            if hid:
                self.ids.setdefault(norm(" ".join(self._text)), hid)
            self._level, self._section = 0, None

    def handle_data(self, data):
        if self._level:
            self._text.append(data)
        elif data.strip():
            self._section = None


def heading_ids(page_html: str) -> dict[str, str]:
    parser = HeadingIds()
    try:
        parser.feed(page_html)
    except Exception:  # broken HTML: heading anchors are a nice-to-have
        return {}
    return parser.ids


def norm(text: str) -> str:
    """Heading text for matching: letters, digits and single spaces only. Docs generators add a `¶` permalink
    (Sphinx, MkDocs) or a zero-width space (Docusaurus) inside the heading."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", html.unescape(text))).strip().lower()


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


ESCAPE_RE = re.compile(r"\\([!-/:-@\[-`{-~])")  # a CommonMark backslash escape: \_ \* \[ \. ...


def block_words(block: str) -> list[str]:
    """Words of a block as the browser shows them: list and quote markers, link targets, images, backticks
    and emphasis marks removed (the underscore in snake_case stays: the page shows it), and backslash escapes
    (defuddle writes `snake\\_case`, `1\\.`) turned back into their character."""
    text = ESCAPE_RE.sub(lambda m: f"\ue000{ord(m.group(1)):x}\ue001", block)  # out of the way of the rules below
    text = re.sub(r"^\s*(?:(?:>\s*)+|(?:[-*+]|\d+[.)])\s+)", "", text, flags=re.M)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"(?<!\w)[*_]+|[*_]+(?!\w)|`", "", text)
    text = re.sub(r"\ue000([0-9a-f]+)\ue001", lambda m: chr(int(m.group(1), 16)), text)
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


def anchor(markdown: str, url: str, ids: dict[str, str] | None = None, preamble: str = "") -> str:
    """Add [¶n](url#:~:text=...) to every paragraph/list/quote and [#](url#id) to headings with a known id.

    A browser jumps to the first match anywhere on the page, ignoring case, so a fragment grows (up to
    MAX_FRAGMENT_WORDS) until its first match in the page text (`preamble`, e.g. the title, then every block)
    is its own paragraph."""
    base = page_url(url)
    ids = {} if "#" in base else ids or {}  # an #id would replace the app route
    parts = blocks(markdown)
    words = [block_words(lead(b)) if kind(b) == "text" else [] for b in parts]
    page, starts = " " + " ".join(preamble.split()).lower(), []
    for b in parts:
        starts.append(len(page) + 1)
        page += " " + " ".join(block_words(b) if kind(b) != "code" else b.split()).lower()
    out, n = [], 0
    for i, block in enumerate(parts):
        k = kind(block)
        if k == "heading":
            block = PERMALINK_RE.sub("", block)
            hid = ids.get(norm(" ".join(block_words(block.lstrip("#")))))
            out.append(f"{block} [#]({base}#{quote_id(hid)})" if hid else block)
            continue
        if k != "text" or not words[i]:
            out.append(block)
            continue
        n += 1
        count = min(FRAGMENT_WORDS, len(words[i]))
        while count < min(MAX_FRAGMENT_WORDS, len(words[i])) and \
                page.find(" " + " ".join(words[i][:count]).lower()) + 1 != starts[i]:
            count += 1
        link = f"[¶{n}]({base}{fragment(words[i][:count], base)})"
        first, _, rest = block.partition("\n")
        m = re.match(r"^(\s*(?:[-*+]|\d+[.)]|>)\s+)", first)
        first = f"{m.group(1)}{link} {first[m.end():]}" if m else f"{link} {first}"
        out.append(first + ("\n" + rest if rest else ""))
    return "\n\n".join(out)


# a docs generator's own heading permalink ("¶", "#", "§", "🔗" or empty text) at the end of a heading: its URL
# is often mangled by the extractor, and the heading gets our own [#] link instead
PERMALINK_RE = re.compile(r"\s*\[(?:[¶#§]|🔗|\u200b)?\]\([^)\s]*\)\s*$")


def quote_id(hid: str) -> str:
    """A heading id from the page, percent-encoded for a URL fragment inside a markdown link (spaces and
    parentheses too: they would end the link)."""
    return urllib.parse.quote(hid, safe="-._~!$&'*+,;=:@/?")


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


def canonical_url(url: str, final_url: str, declared: str | None) -> str:
    """The page's own URL: its declared canonical/og:url when it names the same path on the same site (it drops
    a query variant or picks http(s)/www), else the URL after redirects. A canonical with another path is not
    trusted: misconfigured sites point every post at /blog/ or every page at page 1. An app route (`#/page`) is
    kept: both of those drop it."""
    if is_route_fragment(urllib.parse.urlsplit(url).fragment):
        return page_url(url)
    if declared and re.match(r"https?://", declared) and host_of(declared) == host_of(final_url) and \
            urllib.parse.urlsplit(declared).path.rstrip("/") == urllib.parse.urlsplit(final_url).path.rstrip("/"):
        return page_url(declared)
    return page_url(final_url)


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

    page = extract(page_url(r["url"]))
    best, m = page.best, page.best.meta
    url = canonical_url(r["url"], page.final_url, m.get("url"))
    # the same page reached by a short link, a permanent redirect or a URL variant: one folder, known by every id
    # (a temporary redirect, like /latest or a locale switch, may lead somewhere else next time)
    ids = list(dict.fromkeys([clean_url(url), *([r["id"]] if page.permanent else []),
                              clean_url(page_url(page.final_url))]))
    for other in ids:
        existing = existing or find_by_id("web", other)
    if existing and (existing / "content.md").exists() and not args.refresh:
        log(f"reusing: {existing}, the same page as {args.url} (pass --refresh to refetch)")
        old = read_json(existing / "metadata.json")
        extras = (old.get("extras") or {}) | {"aliases": aliases_of(old, old.get("id"), ids)}
        meta = update_json(existing / "metadata.json", {"extras": extras})
        return print_envelope(existing, meta, reused=True)
    old = read_json(existing / "metadata.json") if existing else {}
    id_ = old.get("id") or ids[0]

    title = m.get("title") or urllib.parse.urlsplit(url).path.strip("/").split("/")[-1] or url
    host = urllib.parse.urlsplit(url).hostname or ""
    extras = {k: v for k, v in {"description": m.get("description"), "language": m.get("language"),
                                "image": m.get("image"), "attempts": page.attempts, "snapshot": page.snapshot,
                                "gone": page.gone, "aliases": aliases_of(old, id_, ids)}.items() if v}
    meta = {
        "source": "web", "id": id_, "url": url, "title": title, "author": m.get("author"),
        "published": fmt_date(m.get("published")), "fetched": datetime.now().isoformat(timespec="seconds"),
        "site": m.get("site") or re.sub(r"^www\.", "", host), "word_count": best.words, "duration": None,
        "extractor": best.extractor, "content_file": "content.md", "extras": extras,
    }
    folder = existing or unique_dir(meta)
    folder.mkdir(parents=True, exist_ok=True)
    log(f"{'refreshing' if existing else 'folder'}: {folder}")
    # text from an archived copy: the anchors open the snapshot (the live page is gone or cut off)
    body = anchor(best.markdown, page.snapshot or url, heading_ids(best.html) if best.html else {}, preamble=title)
    (folder / "content.md").write_text(render_content(meta, extras, body), encoding="utf-8")
    meta = update_json(folder / "metadata.json", meta | {"prepared_at": old.get("prepared_at") or meta["fetched"]})
    return print_envelope(folder, meta, reused=bool(existing))


def aliases_of(old: dict, id_: str | None, ids: list[str]) -> list[str]:
    """The other ids this page is known by (find_by_id matches them too): the earlier ones plus these."""
    known = list((old.get("extras") or {}).get("aliases") or []) + ids
    return [i for i in dict.fromkeys(known) if i != id_]


def print_envelope(folder: Path, meta: dict, reused: bool) -> int:
    extras = meta.get("extras") or {}
    print(json.dumps(envelope(folder, meta, "page", reused=reused, site=meta.get("site"),
                              words=meta.get("word_count"), extractor=meta.get("extractor"),
                              snapshot=extras.get("snapshot"), gone=extras.get("gone"),
                              attempts=extras.get("attempts")),
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    run_main(main)

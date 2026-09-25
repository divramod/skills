#!/usr/bin/env python3
"""Extract the main text of a web page as markdown + metadata, with the best extractor available.

1. Fetch the HTML once (urllib, browser user agent).
2. Run trafilatura (`uvx trafilatura --markdown --with-metadata`) and defuddle (`npx -y defuddle parse --markdown
   --json`) on it in parallel; score both (main-content words minus boilerplate lines) and keep the better text.
   Metadata is merged: defuddle (schema.org) first, trafilatura fills the gaps.
3. Under MIN_WORDS words (a JS-rendered page, a paywall teaser) or when the fetch fails: Jina Reader
   (`r.jina.ai/<url>`, renders JavaScript), then the latest Wayback Machine snapshot (extractors again).
Every step is logged to stderr; when all fail the error lists what was tried.

Usage: extract.py <url>   (prints {markdown, meta, extractor, attempts} as JSON; prepare.py imports extract())
Requires: uvx, npx.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

from _common import SkillError, log, require, run_main

MIN_WORDS = 200
TIMEOUT = 60  # seconds per extractor / request
JINA = "https://r.jina.ai/"
WAYBACK_API = "https://archive.org/wayback/available?url="
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/128.0 Safari/537.36")
# Lines that are page furniture, not article text: they lower an extraction's score.
BOILERPLATE_RE = re.compile(
    r"^\W*(share (this|on)|subscribe|sign (up|in)|log ?in|cookie|accept all|newsletter|follow us|related (posts|articles)"
    r"|read more|advertisement|all rights reserved|©|copyright|skip to (main )?content|leave a (comment|reply)"
    r"|previous post|next post|tags?:|posted in)", re.I)
# Section headings whose whole section is page furniture.
FURNITURE_HEADING_RE = re.compile(
    r"^\W*((more|other|recent|latest|popular|related)( recent)? (posts|articles|stories|reads)|you (may|might) also like"
    r"|comments|share this|further posts)\W*$", re.I)
LINK_DENSITY = 0.6  # a block whose words are at least this share link text (with 2+ links) is a link list


GONE = (404, 410)  # the page no longer exists: only an archived copy can help


class HttpError(SkillError):
    def __init__(self, code: int, url: str):
        super().__init__(f"HTTP {code} from {url}")
        self.code = code


@dataclass
class Extraction:
    markdown: str
    meta: dict = field(default_factory=dict)
    extractor: str = ""
    html: str = ""  # the page the text came from (for heading ids); empty for Jina

    @property
    def words(self) -> int:
        return word_count(self.markdown)


# ---------------------------------------------------------------- pure helpers


def plain_text(markdown: str) -> str:
    """Markdown -> text: link/image targets, code fences, emphasis and heading marks removed."""
    text = re.sub(r"```.*?```", " ", markdown, flags=re.S)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_`#>|]+", " ", text)
    return text


def word_count(markdown: str) -> int:
    return len(re.findall(r"\w+", plain_text(markdown)))


def is_boilerplate(block: str) -> bool:
    """A furniture line ("Share this", "Related posts") or a link list: mostly link text, several links."""
    if any(BOILERPLATE_RE.match(plain_text(line)) for line in block.splitlines()):
        return True
    links = re.findall(r"(?<!!)\[([^\]]*)\]\([^)]*\)", block)
    words = word_count(block)
    return len(links) >= 2 and words > 0 and sum(word_count(t) for t in links) / words >= LINK_DENSITY


def score(markdown: str) -> int:
    """Content words (code included: a fenced snippet is content) minus the words of boilerplate blocks
    (counted twice: they also inflated the total). A section under a furniture heading ("More recent
    articles") is boilerplate as a whole."""
    total = len(re.findall(r"\w+", plain_text(re.sub(r"^\s*(?:>\s*)*```.*$", "", markdown, flags=re.M))))
    boiler, in_furniture = 0, False
    for block in re.split(r"\n\s*\n", markdown):
        heading = re.match(r"#{1,6}\s+(.*)", block.strip())
        if heading and not block.strip().startswith("```"):
            in_furniture = bool(FURNITURE_HEADING_RE.match(heading.group(1)))
        if in_furniture or is_boilerplate(block):
            boiler += word_count(block)
    return total - 2 * boiler


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """trafilatura's `---\\nkey: value\\n---` header -> (dict, body)."""
    m = re.match(r"\A---\n(.*?)\n---\n?", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        key, sep, val = line.partition(":")
        if sep:
            meta[key.strip()] = val.strip().strip('"').strip("'")
    return meta, text[m.end():]


def from_trafilatura(output: str) -> Extraction:
    meta, body = parse_frontmatter(output)
    body = body.strip()
    title = meta.get("title")
    if title:  # trafilatura repeats the title as the first heading
        body = re.sub(rf"\A#+ {re.escape(title)}\s*\n+", "", body)
    return Extraction(body, {
        "title": title, "author": meta.get("author"), "published": meta.get("date"),
        "site": meta.get("sitename") or meta.get("hostname"), "description": meta.get("description"),
        "url": meta.get("url"), "language": meta.get("language"), "image": meta.get("image"),
    }, "trafilatura")


def from_defuddle(output: str) -> Extraction:
    data = json.loads(output)
    schema = data.get("schemaOrgData") or []
    schema = schema[0] if isinstance(schema, list) and schema else schema if isinstance(schema, dict) else {}
    published = data.get("published") or schema.get("datePublished")
    return Extraction((data.get("content") or "").strip(), {
        "title": data.get("title") or schema.get("headline"), "author": data.get("author"),
        "published": published[:10] if published else None, "site": data.get("site") or data.get("domain"),
        "description": data.get("description"), "language": data.get("language"), "image": data.get("image"),
    }, "defuddle")


def from_jina(output: str) -> Extraction:
    """r.jina.ai answers `Title: ...\\n\\nURL Source: ...\\n\\nMarkdown Content:\\n<markdown>`.
    Its `Published Time` is often the fetch time, so it is not used."""
    head, sep, body = output.partition("Markdown Content:")
    if not sep:
        return Extraction(output.strip(), {}, "jina")
    fields = dict(re.findall(r"^([A-Z][\w ]+): (.*)$", head, re.M))
    return Extraction(body.strip(), {"title": fields.get("Title"), "url": fields.get("URL Source")}, "jina")


def merge_meta(*metas: dict) -> dict:
    """First non-empty value per key, in the order given."""
    out: dict = {}
    for meta in metas:
        for k, v in meta.items():
            if v not in (None, "", []) and out.get(k) in (None, "", []):
                out[k] = v
    return out


def pick(candidates: list[Extraction]) -> Extraction | None:
    """The highest-scoring extraction; its metadata merged with the others' (defuddle first)."""
    good = [c for c in candidates if c.markdown]
    if not good:
        return None
    best = max(good, key=lambda c: score(c.markdown))
    order = sorted(candidates, key=lambda c: c.extractor != "defuddle")
    return Extraction(best.markdown, merge_meta(*(c.meta for c in order)), best.extractor)


def strip_data_links(markdown: str) -> str:
    """`[text](data:...)` -> `text`: an inline file (a "Download" button) is not a link a reader can follow, and its
    payload may hold spaces and parentheses. The target ends at its balanced `)`, else at the end of the line."""
    out, pos = [], 0
    for m in re.finditer(r"\[([^\]]*)\]\(data:", markdown):
        if m.start() < pos:
            continue
        depth, end = 1, m.end()
        while end < len(markdown) and markdown[end] != "\n" and depth:
            depth += {"(": 1, ")": -1}.get(markdown[end], 0)
            end += 1
        out += [markdown[pos:m.start()], m.group(1)]
        pos = end
    return "".join(out) + markdown[pos:]


def normalize(markdown: str) -> str:
    """Data links reduced to their text, a blank line before every heading (Jina and some extractors glue it to the
    line above, which would merge two blocks), at most one blank line in a row; fenced code is left alone."""
    out: list[str] = []
    fence = False
    for line in strip_data_links(markdown).splitlines():
        if line.lstrip(" >").startswith("```"):
            fence = not fence
        elif not fence and re.match(r"#{1,6}\s", line) and out and out[-1].strip():
            out.append("")
        if not line.strip() and out and not out[-1].strip() and not fence:
            continue
        out.append(line.rstrip() if not fence else line)
    return "\n".join(out).strip()


def absolutize(markdown: str, base: str) -> str:
    """Relative link and image targets -> absolute URLs."""
    def fix(m: re.Match) -> str:
        target = m.group(2)
        if re.match(r"^([a-z][a-z0-9+.-]*:|#)", target, re.I):
            return m.group(0)
        return f"{m.group(1)}({urllib.parse.urljoin(base, target)})"
    return re.sub(r"(!?\[[^\]]*\])\(([^)\s]+)\)", fix, markdown)


# ---------------------------------------------------------------- side effects


def http_get(url: str, timeout: int = TIMEOUT, accept: str = "text/html,*/*",
             headers: dict | None = None) -> tuple[str, str]:
    """(body, final URL). Raises SkillError with the HTTP status or network error."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept,
                                               "Accept-Language": "en;q=0.9,*;q=0.5"} | (headers or {}))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            charset = r.headers.get_content_charset() or "utf-8"
            return r.read().decode(charset, errors="replace"), r.geturl()
    except urllib.error.HTTPError as e:
        raise HttpError(e.code, url)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise SkillError(f"could not fetch {url}: {getattr(e, 'reason', e)}")


def run_tool(name: str, cmd: list[str], stdin: str | None = None) -> str:
    try:
        p = subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        raise SkillError(f"{name} timed out after {TIMEOUT}s")
    if p.returncode != 0 or p.stdout.startswith("Error:"):  # defuddle prints "Error: ..." on stdout
        out = p.stderr.strip() or p.stdout.strip()
        raise SkillError(out.splitlines()[-1] if out else f"{name} exited {p.returncode}")
    return p.stdout


def trafilatura(html: str) -> Extraction:
    return from_trafilatura(run_tool("trafilatura", ["uvx", "trafilatura", "--markdown", "--with-metadata",
                                                     "--formatting", "--links", "--no-comments"], stdin=html))


def defuddle(html: str) -> Extraction:
    return from_defuddle(run_tool("defuddle", ["npx", "-y", "defuddle", "parse", "-", "--markdown", "--json"],
                                  stdin=html))


def jina(url: str) -> Extraction:
    """r.jina.ai renders the page in a browser. It refuses browser user agents (403), and a `#` in the target
    must be encoded or it drops a single-page app's route."""
    body, _ = http_get(JINA + url.replace("#", "%23"), accept="text/plain",
                       headers={"User-Agent": "tell-me", "X-Timeout": "30", "X-No-Cache": "true"})
    return from_jina(body)


def extract_html(html: str, base: str, attempts: list[str], label: str = "") -> Extraction | None:
    """Both extractors in parallel on the same HTML; the better one (or None)."""
    results = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {name: pool.submit(fn, html) for name, fn in (("trafilatura", trafilatura), ("defuddle", defuddle))}
        for name, fut in futures.items():
            try:
                ex = fut.result()
                attempts.append(f"{label}{name}: {ex.words} words")
                results.append(ex)
            except (SkillError, json.JSONDecodeError) as e:
                attempts.append(f"{label}{name}: failed ({e})")
    best = pick(results)
    if best:
        best.markdown = normalize(absolutize(best.markdown, base))
        best.extractor = label + best.extractor
        best.html = html
    return best


def wayback_snapshot(url: str) -> str | None:
    """URL of the latest archived copy (the page with the Wayback toolbar, for people), or None."""
    body, _ = http_get(WAYBACK_API + urllib.parse.quote(url, safe=""), accept="application/json")
    try:
        snap = (json.loads(body).get("archived_snapshots") or {}).get("closest") or {}
    except json.JSONDecodeError:
        raise SkillError("the Wayback Machine answered with something that is not JSON")
    return re.sub(r"^http:", "https:", snap["url"]) if snap.get("available") and snap.get("url") else None


def raw_snapshot(snapshot: str) -> str:
    """The archived page as it was, without the Wayback toolbar and rewritten links (the `id_` flag)."""
    return re.sub(r"(/web/\d+)(/)", r"\1id_\2", snapshot, count=1)


def extract(url: str) -> tuple[Extraction, list[str], str | None]:
    """(best extraction, attempts log, wayback snapshot URL or None). SkillError when nothing worked."""
    require("uvx", "npx")
    attempts: list[str] = []
    best = None
    final_url = url
    gone = 0  # the HTTP status when the page no longer exists
    try:
        html, final_url = http_get(url)
        log(f"fetched {final_url} ({len(html) // 1024} KB); running trafilatura + defuddle")
        best = extract_html(html, final_url, attempts)
    except SkillError as e:
        attempts.append(f"fetch: {e}")
        gone = e.code if isinstance(e, HttpError) and e.code in GONE else 0
    if best and best.words >= MIN_WORDS:
        log(f"{'; '.join(attempts)} -> using {best.extractor}")
        return best, attempts, None

    if gone:  # Jina would only render the error page
        attempts.append("jina: skipped (the page is gone)")
    else:
        log(f"{'; '.join(attempts)} -> under {MIN_WORDS} words, trying Jina Reader (renders JavaScript)")
        try:
            rendered = jina(url)
            rendered.markdown = normalize(absolutize(rendered.markdown, final_url))
            attempts.append(f"jina: {rendered.words} words")
            if rendered.words >= MIN_WORDS:
                rendered.meta = merge_meta(best.meta if best else {}, rendered.meta)
                log(f"{attempts[-1]} -> using jina")
                return rendered, attempts, None
            best = best if best and best.words >= rendered.words else rendered
        except SkillError as e:
            attempts.append(f"jina: failed ({e})")

    log(f"{attempts[-1]} -> trying the Wayback Machine")
    snapshot = None
    try:
        snapshot = wayback_snapshot(url)
        if snapshot:
            html, _ = http_get(raw_snapshot(snapshot))
            archived = extract_html(html, final_url, attempts, label="wayback+")
            if archived and (not best or archived.words > best.words):
                best = archived
        else:
            attempts.append("wayback: no snapshot")
    except SkillError as e:
        attempts.append(f"wayback: failed ({e})")
    log("; ".join(attempts))
    if gone and not (best and best.extractor.startswith("wayback+")):
        raise SkillError(f"{url} is gone (HTTP {gone}) and the Wayback Machine has no usable copy. Tried: "
                         + "; ".join(attempts[1:]))
    if not best or not best.words:
        raise SkillError(f"no text could be extracted from {url}. Tried: " + "; ".join(attempts))
    if best.words < MIN_WORDS:
        log(f"only {best.words} words: paywall, login wall or a mostly-visual page")
    return best, attempts, snapshot if best.extractor.startswith("wayback+") else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    args = ap.parse_args(argv)
    best, attempts, snapshot = extract(args.url)
    print(json.dumps({"markdown": best.markdown, "meta": best.meta, "extractor": best.extractor, "words": best.words,
                      "attempts": attempts, "snapshot": snapshot}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    run_main(main)

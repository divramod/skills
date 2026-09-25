#!/usr/bin/env python3
"""Extract the main text of a web page as markdown + metadata, with the best extractor available.

1. Fetch the HTML once (urllib, browser user agent; a PDF or other document is refused: that's the file source).
2. Run trafilatura (`uvx trafilatura --markdown --with-metadata`) and defuddle (`npx -y defuddle parse --markdown
   --json`), both pinned, on it in parallel; score both (content words, code included, minus boilerplate) and keep
   the better text. Metadata is merged: defuddle (schema.org) first, trafilatura fills the gaps.
3. Under MIN_WORDS words (a JS-rendered page, a paywall teaser) or when the fetch fails: Jina Reader
   (`r.jina.ai/<url>`, renders JavaScript), then the latest Wayback Machine snapshot (extractors again). A page
   that is gone (404/410) skips Jina, and fails when the archive has no copy either.
Links other than http(s)/mailto are reduced to their text. Every step is logged to stderr; when all fail the
error lists what was tried.

Usage: extract.py <url>   (prints {markdown, meta, extractor, words, attempts, final_url, snapshot, gone} as JSON;
prepare.py imports extract())
Requires: uvx, npx.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import shlex
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
from route import host_of

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
MAX_BYTES = 10 * 1024 * 1024  # read at most this much of a page
TEXT_TYPE_RE = re.compile(r"^(text/|application/(xhtml\+xml|xml|json|.*\+xml$))")
# Extractor versions, pinned: they parse untrusted pages, and a new release may change their output format.
TRAFILATURA = "trafilatura==2.2.0"
DEFUDDLE = "defuddle@0.19.4"
WARM_TIMEOUT = 600  # the first download of either package


class HttpError(SkillError):
    def __init__(self, code: int, url: str, body: str = ""):
        super().__init__(f"HTTP {code} from {url}")
        self.code, self.body = code, body


class NotAPage(SkillError):
    """The URL serves a document (PDF, image, ...): no extractor or fallback can help."""


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
    """Markdown -> text: fence lines, images, link targets, emphasis and heading marks removed. Code inside
    fences stays: a snippet is content (a tutorial may be mostly code)."""
    text = re.sub(r"^\s*(?:>\s*)*```.*$", " ", markdown, flags=re.M)
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
    """Content words (code included) minus the words of boilerplate blocks (counted twice: they also
    inflated the total). A section under a furniture heading ("More recent articles") is boilerplate as a
    whole."""
    total = word_count(markdown)
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


def iso_day(value) -> str | None:
    """YYYY-MM-DD of an ISO date/time, else None. defuddle passes dates on as the page writes them ("March 5,
    2024"): those are left to trafilatura, which normalizes them."""
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(value or ""))
    return m.group(1) if m else None


def from_defuddle(output: str) -> Extraction:
    data = json.loads(output)
    if not isinstance(data, dict):
        raise SkillError("defuddle answered no JSON object")
    schema = data.get("schemaOrgData") or []
    schema = schema[0] if isinstance(schema, list) and schema else schema
    schema = schema if isinstance(schema, dict) else {}  # malformed schema.org data is ignored
    return Extraction((data.get("content") or "").strip(), {
        "title": data.get("title") or schema.get("headline"), "author": data.get("author"),
        "published": iso_day(data.get("published")) or iso_day(schema.get("datePublished")), "site": data.get("site") or data.get("domain"),
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


def strip_unsafe_links(markdown: str) -> str:
    """`[text](<scheme>:...)` -> `text` for every scheme but http(s) and mailto: an inline file (a "Download"
    button's data: URL) is not a link a reader can follow, and javascript: must never reach a page. The target
    may hold spaces and parentheses: it ends at its balanced `)`, else at the end of the line."""
    out, pos = [], 0
    # the label has no brackets: in [![logo](data:...)](https://home) only the inner image is unsafe
    for m in re.finditer(r"!?\[([^\[\]]*)\]\(\s*(?!(?:https?|mailto):)[a-z][a-z0-9+.-]*:", markdown, re.I):
        if m.start() < pos:
            continue
        depth, end = 1, m.end()
        while end < len(markdown) and markdown[end] != "\n" and depth:
            depth += {"(": 1, ")": -1}.get(markdown[end], 0)
            end += 1
        out += [markdown[pos:m.start()], m.group(1)]
        pos = end
    return "".join(out) + markdown[pos:]


def outside_code(line: str, fn) -> str:
    """fn applied to the parts of a line that are not `code spans`."""
    return "".join(part if i % 2 else fn(part) for i, part in enumerate(re.split(r"(`+[^`]*`+)", line)))


def normalize(markdown: str) -> str:
    """Control characters dropped; outside fenced code: non-web links (data:, javascript:) reduced to their text
    (not inside `code spans`), a heading set apart by blank lines (Jina and some extractors glue it to the lines
    around it, which would merge blocks) and at most one blank line in a row."""
    out: list[str] = []
    fence = heading = False
    for line in re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", markdown).splitlines():
        if line.lstrip(" >").startswith("```"):
            fence = not fence
            if heading:
                out.append("")
            heading = False
        elif not fence:
            line = outside_code(line, strip_unsafe_links)
            is_heading = bool(re.match(r"#{1,6}\s", line))
            if (is_heading or heading) and line.strip() and out and out[-1].strip():
                out.append("")
            heading = is_heading
        if not line.strip() and out and not out[-1].strip() and not fence:
            continue
        out.append(line.rstrip() if not fence else line)
    return "\n".join(out).strip()


def absolutize(markdown: str, base: str) -> str:
    """Relative link and image targets (and `#section`) -> absolute URLs."""
    def fix(m: re.Match) -> str:
        target = m.group(2)
        if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
            return m.group(0)
        return f"{m.group(1)}({urllib.parse.urljoin(base, target)})"
    return re.sub(r"(!?\[[^\]]*\])\(([^)\s]+)\)", fix, markdown)


# ---------------------------------------------------------------- side effects


def decode(data: bytes, header_charset: str | None) -> str:
    """Bytes -> text with the HTTP header's charset, else the page's own <meta charset>, else UTF-8, else
    Windows-1252 (old pages that declare nothing)."""
    charset = header_charset
    if not charset:
        m = re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", data[:4096], re.I)
        if not m:
            try:
                return data.decode("utf-8")
            except UnicodeDecodeError:
                return data.decode("cp1252", errors="replace")
        charset = m.group(1).decode("ascii")
    try:
        return data.decode(charset, errors="replace")
    except LookupError:  # an unknown charset name
        return data.decode("utf-8", errors="replace")


class RedirectLog(urllib.request.HTTPRedirectHandler):
    """Follows redirects like the default handler and notes their status codes on the final response."""

    def http_error_302(self, req, fp, code, msg, headers):
        r = super().http_error_302(req, fp, code, msg, headers)
        if r is not None:
            r.redirect_codes = [code] + getattr(r, "redirect_codes", [])
        return r

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


def open_url(req: urllib.request.Request, timeout: int):
    return urllib.request.build_opener(RedirectLog).open(req, timeout=timeout)


def http_get(url: str, timeout: int = TIMEOUT, accept: str = "text/html,*/*",
             headers: dict | None = None) -> tuple[str, str, bool]:
    """(body, final URL, whether every redirect on the way was permanent: 301/308). Raises HttpError with the
    status (and the error page), NotAPage for a PDF or another non-text document, SkillError for a network
    error."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept,
                                               "Accept-Language": "en;q=0.9,*;q=0.5"} | (headers or {}))
    try:
        with open_url(req, timeout) as r:
            ctype = r.headers.get_content_type()
            if not TEXT_TYPE_RE.match(ctype):
                raise NotAPage(f"{url} is a {ctype} document, not a web page: summarize it as a file "
                               f"(python3 scripts/file/prepare.py {shlex.quote(url)})")
            permanent = all(c in (301, 308) for c in getattr(r, "redirect_codes", []))
            return decode(r.read(MAX_BYTES), r.headers.get_content_charset()), r.geturl(), permanent
    except urllib.error.HTTPError as e:
        body = decode(e.read(MAX_BYTES), e.headers.get_content_charset() if e.headers else None)
        raise HttpError(e.code, url, body)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise SkillError(f"could not fetch {url}: {getattr(e, 'reason', e)}")


def run_tool(name: str, cmd: list[str], stdin: str | None = None, timeout: int = TIMEOUT) -> str:
    try:
        p = subprocess.run(cmd, input=stdin, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        raise SkillError(f"{name} timed out after {timeout}s")
    if p.returncode != 0 or p.stdout.startswith("Error:"):  # defuddle prints "Error: ..." on stdout
        out = p.stderr.strip() or p.stdout.strip()
        raise SkillError(out.splitlines()[-1] if out else f"{name} exited {p.returncode}")
    return p.stdout


def trafilatura(html: str) -> Extraction:
    return from_trafilatura(run_tool("trafilatura", ["uvx", TRAFILATURA, "--markdown", "--with-metadata",
                                                     "--formatting", "--links", "--no-comments"], stdin=html))


def defuddle(html: str) -> Extraction:
    return from_defuddle(run_tool("defuddle", ["npx", "-y", DEFUDDLE, "parse", "-", "--markdown", "--json"],
                                  stdin=html))


def jina(url: str) -> Extraction:
    """r.jina.ai renders the page in a browser. It refuses browser user agents (403), and a `#` in the target
    must be encoded or it drops a single-page app's route."""
    body, _, _ = http_get(JINA + url.replace("#", "%23"), accept="text/plain",
                       headers={"User-Agent": "tell", "X-Timeout": "30", "X-No-Cache": "true"})
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
            except Exception as e:  # one extractor failing (bad output, a crash) never loses the other's text
                attempts.append(f"{label}{name}: failed ({e})")
    best = pick(results)
    if best:
        best.markdown = normalize(absolutize(best.markdown, base))
        best.extractor = label + best.extractor
        best.html = html
    return best


def wayback_snapshot(url: str) -> str | None:
    """URL of the latest archived copy (the page with the Wayback toolbar, for people), or None."""
    body, _, _ = http_get(WAYBACK_API + urllib.parse.quote(url, safe=""), accept="application/json")
    try:
        snap = (json.loads(body).get("archived_snapshots") or {}).get("closest") or {}
    except json.JSONDecodeError:
        raise SkillError("the Wayback Machine answered with something that is not JSON")
    if not (snap.get("available") and snap.get("url") and str(snap.get("status", "200")).startswith("2")):
        return None  # none, or an archived error page / redirect
    return re.sub(r"^http:", "https:", snap["url"])


def raw_snapshot(snapshot: str) -> str:
    """The archived page as it was, without the Wayback toolbar and rewritten links (the `id_` flag)."""
    return re.sub(r"(/web/\d+)(/)", r"\1id_\2", snapshot, count=1)


@dataclass
class Page:
    best: Extraction
    attempts: list[str]
    final_url: str  # after redirects
    snapshot: str | None = None  # the Wayback copy the text came from
    gone: int = 0  # 404/410: the live page no longer exists
    permanent: bool = True  # no redirect, or only permanent ones: the URL asked for names this page for good


def is_app_shell(html: str) -> bool:
    """A near-empty page that loads scripts: a single-page app. Such a site may answer 404 for every deep link
    (GitHub Pages' 404.html fallback) and still render the page in a browser."""
    text = re.sub(r"<(script|style)\b.*?</\1>|<[^>]+>", " ", html, flags=re.S | re.I)
    return bool(re.search(r"<script\b", html, re.I)) and len(text.split()) < 50


def is_soft_404(url: str, final_url: str) -> bool:
    """An article's link that redirects to a site's home page: the page is gone (dead GeoCities pages land on
    Yahoo, removed posts on the blog's front page). Only article-shaped paths count (two segments or more, or a
    file name): a short link (t.co/abc) or a locale (/en) may rightly lead to a home page."""
    def path(u: str) -> str:
        return re.sub(r"/(index|default)\.\w+$", "/", urllib.parse.urlsplit(u).path).strip("/")
    source = path(url)
    article = source.count("/") >= 1 or bool(re.search(r"\.\w{2,5}$", source))
    same_site = host_of(url) == host_of(final_url)
    # on the same site, a query may still select the page (/?p=123)
    return article and not path(final_url) and (not same_site or not urllib.parse.urlsplit(final_url).query)


CHALLENGE_RE = re.compile(r"just a moment|checking your browser|verify (that )?you are (a )?human|attention required|"
                          r"access denied|forbidden|page not found|not found|enable javascript|captcha", re.I)


def is_error_page(ex: Extraction) -> bool:
    """A short text that is a bot challenge or an error page, not a short article."""
    return ex.words < MIN_WORDS and (ex.words < 50 or bool(CHALLENGE_RE.search(ex.markdown[:600])))


def is_private(url: str) -> bool:
    """localhost, a LAN/intranet address or a single-label/.local/.internal host: never sent to Jina or the
    Wayback Machine (the URL may carry a token, and they could not reach it anyway)."""
    host = (urllib.parse.urlsplit(url).hostname or "").rstrip(".")
    try:
        return not ipaddress.ip_address(host).is_global
    except ValueError:
        return "." not in host or host.endswith((".local", ".internal", ".lan", ".home.arpa", ".localhost"))


# a consent/login host, or one of those as a whole path segment (not /login-flows-explained/)
WALL_RE = re.compile(r"^(consent|login|signin|accounts?|auth)\.[^/]+\.|"
                     r"/(consent|collectconsent|login|signin|sign-in|sso|auth)(/|$)", re.I)


def is_wall(url: str, final_url: str) -> bool:
    """A redirect to a cookie-consent or login page (consent.yahoo.com, /login?next=...): that page is not the
    article. Jina Reader (which fetches from elsewhere) or the archive may still have it."""
    b = urllib.parse.urlsplit(final_url)
    return final_url != url and bool(WALL_RE.search(f"{b.hostname or ''}{b.path}"))


def extract(url: str) -> Page:
    """The best text of the page, with the attempts log. SkillError when nothing worked."""
    require("uvx", "npx")
    attempts: list[str] = []
    best = None
    final_url, permanent = url, True
    gone = wall = status = 0
    try:
        html, final_url, permanent = http_get(url)
        if is_soft_404(url, final_url):
            attempts.append(f"fetch: redirected to the home page {final_url} (the page is gone)")
            gone, final_url = 404, url
        else:
            log(f"fetched {final_url} ({len(html) // 1024} KB); running trafilatura + defuddle")
            best = extract_html(html, final_url, attempts)
            if is_wall(url, final_url) and (not best or best.words < MIN_WORDS):  # the wall's text is no article
                attempts.append(f"fetch: redirected to a consent or login page {final_url}")
                wall, final_url, best = 1, url, None
    except NotAPage:
        raise
    except SkillError as e:
        attempts.append(f"fetch: {e}")
        if isinstance(e, HttpError):
            status = e.code
            if e.code in GONE and not is_app_shell(e.body):
                gone = e.code
    if best and best.words >= MIN_WORDS:
        log(f"{'; '.join(attempts)} -> using {best.extractor}")
        return Page(best, attempts, final_url, permanent=permanent)

    snapshot = None
    if is_private(url):
        attempts.append("jina, wayback: skipped (a private address is not sent to third parties)")
        steps = []
    else:  # Jina follows the same redirect, so behind a wall the archive goes first
        steps = ["wayback", "jina"] if wall else ["jina", "wayback"]
    for step in steps:
        if step == "jina":
            if gone:  # Jina would only render the error page
                attempts.append("jina: skipped (the page is gone)")
                continue
            log(f"{'; '.join(attempts)} -> trying Jina Reader (renders JavaScript)")
            try:
                rendered = jina(url)
                rendered.markdown = normalize(absolutize(rendered.markdown, final_url))
                attempts.append(f"jina: {rendered.words} words")
                if rendered.words >= MIN_WORDS:
                    rendered.meta = merge_meta(best.meta if best else {}, rendered.meta)
                    log(f"{attempts[-1]} -> using jina")
                    return Page(rendered, attempts, final_url, permanent=permanent)
                best = best if best and best.words >= rendered.words else rendered
            except SkillError as e:
                attempts.append(f"jina: failed ({e})")
        else:
            log(f"{'; '.join(attempts)} -> trying the Wayback Machine")
            try:
                snapshot = wayback_snapshot(url)
                if snapshot:
                    html, _, _ = http_get(raw_snapshot(snapshot))
                    archived = extract_html(html, final_url, attempts, label="wayback+")
                    if archived and (not best or archived.words > best.words):
                        best = archived
                else:
                    attempts.append("wayback: no snapshot")
            except SkillError as e:
                attempts.append(f"wayback: failed ({e})")
            if wall and best and best.words >= MIN_WORDS:
                break
    log("; ".join(attempts))
    archived = bool(best and best.extractor.startswith("wayback+"))
    if gone and not archived:
        raise SkillError(f"{url} is gone (HTTP {gone}) and the Wayback Machine has no usable copy. Tried: "
                         + "; ".join(attempts[1:]))
    if not best or not best.words:
        raise SkillError(f"no text could be extracted from {url}. Tried: " + "; ".join(attempts))
    if (status or wall) and not archived and is_error_page(best):  # the rescue only rendered a challenge page
        raise SkillError(f"{url} answered {f'HTTP {status}' if status else 'with a consent or login page'} and "
                         f"no fallback got the article (only {best.words} words). Tried: " + "; ".join(attempts))
    if best.words < MIN_WORDS:
        log(f"only {best.words} words: paywall, login wall or a mostly-visual page")
    return Page(best, attempts, final_url, snapshot if archived else None, gone, permanent)


def warm() -> int:
    """Run both pinned extractors once, so uvx/npx download them without the per-page timeout."""
    require("uvx", "npx")
    for name, cmd in (("trafilatura", ["uvx", TRAFILATURA, "--version"]),
                      ("defuddle", ["npx", "-y", DEFUDDLE, "--version"])):
        log(f"fetching {name} (first time only)")
        run_tool(name, cmd, timeout=WARM_TIMEOUT)
    log("trafilatura and defuddle are ready")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", nargs="?")
    ap.add_argument("--warm", action="store_true",
                    help="download the pinned trafilatura and defuddle now (install-prerequisites.sh runs this)")
    args = ap.parse_args(argv)
    if args.warm:
        return warm()
    if not args.url:
        ap.error("a URL is required")
    page = extract(args.url)
    best = page.best
    print(json.dumps({"markdown": best.markdown, "meta": best.meta, "extractor": best.extractor, "words": best.words,
                      "attempts": page.attempts, "final_url": page.final_url, "snapshot": page.snapshot,
                      "gone": page.gone or None}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    run_main(main)

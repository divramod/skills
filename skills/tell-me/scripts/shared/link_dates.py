#!/usr/bin/env python3
"""Find how current a link is: publish / update dates and versions, per kind of source.

`date_info(url)` returns {kind, label, published?, updated?, version?, released?, last_commit?}
or {} when nothing is known. `label` is the short text the summary shows next to the link:

  youtube video       published 2025-06-03                        (yt-dlp)
  github repo         v1.4.0 released 2026-09-01 · last commit 2026-09-24   (GitHub API; token from
                      $GITHUB_TOKEN / $GH_TOKEN / `gh auth token` when available)
  arxiv paper         published 2023-06-01 · updated 2023-07-12   (arXiv API)
  doi paper           published 2021-03-15                        (Crossref)
  book                first published 2011 · this edition 2013    (Open Library + Google Books, by ISBN)
  wikipedia           last edited 2026-09-20                      (MediaWiki API)
  pypi / npm package  v0.4.2 released 2026-09-10                  (registry JSON)
  hugging face        created 2024-07-23 · updated 2026-08-02     (HF API)
  web page            published 2025-01-10 · updated 2025-03-02   (article:published_time, JSON-LD, <time>)

Usage: link_dates.py <url> [<url> ...]   (prints JSON per URL)
Requires: nothing for most sources; yt-dlp for YouTube videos; gh optional (GitHub rate limit).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
# APIs (Wikipedia, Crossref, Open Library, ...) ask for an honest client name and throttle browser UAs.
API_UA = "tell-me/1.0 (https://github.com/divramod/skills)"
TIMEOUT = 12

# ---------------------------------------------------------------- helpers


def day(value) -> str | None:
    """Normalize '2025-06-03T10:00:00Z' / '20250603' / '2011' / epoch seconds to YYYY-MM-DD (or YYYY[-MM])."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        from datetime import datetime, timezone
        return datetime.fromtimestamp(value, tz=timezone.utc).date().isoformat()
    s = str(value).strip()
    if re.fullmatch(r"\d{9,10}|\d{12,13}", s):  # epoch seconds / milliseconds as text (og:updated_time)
        return day(int(s) / (1000 if len(s) > 11 else 1))
    if re.fullmatch(r"\d{8}", s):
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    m = re.match(r"(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?", s)
    if m:
        y, mo, d = m.groups()
        return y + (f"-{int(mo):02d}" if mo else "") + (f"-{int(d):02d}" if d else "")
    m = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", s)  # "March 2011", "Oct 25, 2011"
    return m.group(1) if m else None


def get(url: str, headers: dict | None = None, raw: bool = False):
    """GET url; JSON unless raw. API calls (JSON) use API_UA, web pages a browser UA. One retry on 429."""
    import time
    ua = UA if raw and "api" not in urllib.parse.urlsplit(url).netloc else API_UA
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Language": "en", **(headers or {})})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                data = r.read(2_000_000)
                return data.decode("utf-8", "replace") if raw else json.loads(data)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt:
                raise
            e.close()
            time.sleep(min(float(e.headers.get("Retry-After") or 2), 10))


def join(*parts: str | None) -> str:
    return " · ".join(p for p in parts if p)


# ---------------------------------------------------------------- sources


def youtube_id(url: str) -> str | None:
    u = urllib.parse.urlsplit(url)
    host = u.netloc.lower().removeprefix("www.").removeprefix("m.")
    if host == "youtu.be":
        return u.path.strip("/").split("/")[0] or None
    if host == "youtube.com":
        if u.path == "/watch":
            return (urllib.parse.parse_qs(u.query).get("v") or [None])[0]
        m = re.match(r"/(?:shorts|live|embed)/([\w-]{6,})", u.path)
        return m.group(1) if m else None
    return None


def youtube_dates(video_ids: list[str]) -> dict[str, str]:
    """id -> upload date (YYYY-MM-DD) via yt-dlp, several videos in parallel."""
    if not video_ids:
        return {}
    if not shutil.which("yt-dlp"):
        print("[tell-me] yt-dlp not found: skipping YouTube dates (install: brew install yt-dlp, "
              "or run install-prerequisites.sh)", file=sys.stderr)
        return {}
    from concurrent.futures import ThreadPoolExecutor

    def one(vid: str):
        p = subprocess.run(["yt-dlp", "--no-warnings", "--skip-download", "--print", "%(upload_date)s",
                            f"https://www.youtube.com/watch?v={vid}"], capture_output=True, text=True, timeout=60)
        return vid, day(p.stdout.strip()) if p.returncode == 0 and p.stdout.strip() not in ("", "NA") else None

    with ThreadPoolExecutor(max_workers=6) as pool:
        return {vid: d for vid, d in pool.map(one, video_ids) if d}


@lru_cache(maxsize=1)
def github_token() -> str | None:
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not tok and shutil.which("gh"):
        p = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
        tok = p.stdout.strip() if p.returncode == 0 else None
    return tok or None


def gh(path: str):
    headers = {"Accept": "application/vnd.github+json"}
    if github_token():
        headers["Authorization"] = f"Bearer {github_token()}"
    return get(f"https://api.github.com{path}", headers)


def github(owner: str, repo: str) -> dict:
    info = gh(f"/repos/{owner}/{repo}")
    branch = info.get("default_branch") or "main"
    out: dict = {"kind": "github repo", "created": day(info.get("created_at"))}
    try:
        rel = gh(f"/repos/{owner}/{repo}/releases/latest")
        out.update(version=rel.get("tag_name"), released=day(rel.get("published_at")))
    except urllib.error.HTTPError:  # no releases: fall back to the newest tag
        try:
            tags = gh(f"/repos/{owner}/{repo}/tags?per_page=1")
            if tags:
                out["version"] = tags[0]["name"]
                commit = gh(f"/repos/{owner}/{repo}/commits/{tags[0]['commit']['sha']}")
                out["released"] = day(commit["commit"]["committer"]["date"])
        except (urllib.error.HTTPError, KeyError, IndexError):
            pass
    try:
        commits = gh(f"/repos/{owner}/{repo}/commits?sha={urllib.parse.quote(branch)}&per_page=1")
        out["last_commit"] = day(commits[0]["commit"]["committer"]["date"])
    except (urllib.error.HTTPError, KeyError, IndexError):
        out["last_commit"] = day(info.get("pushed_at"))
    release = f"{out['version']} released {out['released']}" if out.get("version") and out.get("released") else (
        out.get("version") or "no releases")
    out["label"] = join(release, f"last commit {out['last_commit']} on {branch}" if out.get("last_commit") else None)
    return out


def arxiv(paper_id: str) -> dict:
    xml = get(f"https://export.arxiv.org/api/query?id_list={urllib.parse.quote(paper_id)}", raw=True)
    entry = xml.split("<entry>", 1)[-1]
    pub = re.search(r"<published>([^<]+)</published>", entry)
    upd = re.search(r"<updated>([^<]+)</updated>", entry)
    if not pub:
        return {}
    out = {"kind": "arxiv paper", "published": day(pub.group(1)), "updated": day(upd.group(1)) if upd else None}
    same = out["updated"] == out["published"]
    out["label"] = join(f"published {out['published']}", None if same or not out["updated"] else f"updated {out['updated']}")
    return out


def crossref(doi: str) -> dict:
    msg = get(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}")["message"]
    for key in ("published-print", "published-online", "issued", "created"):
        parts = (msg.get(key) or {}).get("date-parts") or [[]]
        if parts[0]:
            d = "-".join(f"{p:02d}" if i else str(p) for i, p in enumerate(parts[0]))
            return {"kind": "paper", "published": d, "label": f"published {d}"}
    return {}


def book(isbn: str) -> dict:
    """First publication year (Open Library) plus this edition's date (Google Books)."""
    first = None
    try:
        docs = get(f"https://openlibrary.org/search.json?isbn={isbn}&fields=first_publish_year").get("docs") or []
        first = str(docs[0]["first_publish_year"]) if docs and docs[0].get("first_publish_year") else None
    except (urllib.error.URLError, ValueError, KeyError):
        pass
    edition = book_edition(isbn)
    published = first or edition
    if not published:
        return {}
    same = not edition or edition[:4] == published[:4]
    return {"kind": "book", "published": published, "edition": edition,
            "label": join(f"first published {published}" if first else f"published {published}",
                          None if same else f"this edition {edition}")}


def book_edition(isbn: str) -> str | None:
    try:
        items = get(f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}").get("items") or []
        if items and items[0].get("volumeInfo", {}).get("publishedDate"):
            return day(items[0]["volumeInfo"]["publishedDate"])
    except (urllib.error.URLError, ValueError, KeyError):
        pass
    try:
        return day(get(f"https://openlibrary.org/isbn/{isbn}.json").get("publish_date"))
    except (urllib.error.URLError, ValueError, KeyError):
        return None


def wikipedia(lang: str, title: str) -> dict:
    q = urllib.parse.urlencode({"action": "query", "prop": "revisions", "rvprop": "timestamp", "titles": title,
                                "format": "json", "redirects": 1})
    pages = get(f"https://{lang}.wikipedia.org/w/api.php?{q}")["query"]["pages"]
    rev = next(iter(pages.values())).get("revisions") or []
    if not rev:
        return {}
    d = day(rev[0]["timestamp"])
    return {"kind": "wikipedia", "updated": d, "label": f"last edited {d}"}


def pypi(name: str) -> dict:
    data = get(f"https://pypi.org/pypi/{name}/json")
    version = data["info"]["version"]
    files = data.get("releases", {}).get(version) or []
    d = day(files[0]["upload_time_iso_8601"]) if files else None
    return {"kind": "pypi package", "version": version, "released": d,
            "label": f"v{version} released {d}" if d else f"v{version}"}


def npm(name: str) -> dict:
    data = get(f"https://registry.npmjs.org/{urllib.parse.quote(name, safe='@')}")
    version = (data.get("dist-tags") or {}).get("latest")
    d = day((data.get("time") or {}).get(version))
    return {"kind": "npm package", "version": version, "released": d,
            "label": f"v{version} released {d}" if d else f"v{version}"}


def huggingface(kind: str, repo_id: str) -> dict:
    api = {"models": "models", "datasets": "datasets", "spaces": "spaces"}[kind]
    data = get(f"https://huggingface.co/api/{api}/{repo_id}")
    created, updated = day(data.get("createdAt")), day(data.get("lastModified"))
    return {"kind": f"hugging face {kind[:-1]}", "published": created, "updated": updated,
            "label": join(f"created {created}" if created else None, f"updated {updated}" if updated else None)}


_META_RE = {
    "published": [r'property=["\']article:published_time["\'][^>]*content=["\']([^"\']+)',
                  r'content=["\']([^"\']+)["\'][^>]*property=["\']article:published_time',
                  r'name=["\'](?:date|pubdate|publish[-_]?date|citation_publication_date|dc\.date)["\'][^>]*content=["\']([^"\']+)',
                  r'itemprop=["\']datePublished["\'][^>]*content=["\']([^"\']+)',
                  r'"datePublished"\s*:\s*"([^"]+)"'],
    "updated": [r'property=["\'](?:article:modified_time|og:updated_time)["\'][^>]*content=["\']([^"\']+)',
                r'content=["\']([^"\']+)["\'][^>]*property=["\'](?:article:modified_time|og:updated_time)',
                r'itemprop=["\']dateModified["\'][^>]*content=["\']([^"\']+)',
                r'"dateModified"\s*:\s*"([^"]+)"'],
}


_MONTHS = {m: i + 1 for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"))}
_TEXT_DATE_RE = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? (\d{1,2}),? (20\d\d)\b"
                           r"|\b(\d{1,2}) (jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? (20\d\d)\b", re.I)


def text_date(m: re.Match) -> str:
    mon, d, y = (m.group(1), m.group(2), m.group(3)) if m.group(1) else (m.group(5), m.group(4), m.group(6))
    return f"{y}-{_MONTHS[mon[:3].lower()]:02d}-{int(d):02d}"


def page_dates(html_text: str, homepage: bool = False) -> dict:
    """Publish/update dates from a web page's metadata (OpenGraph, meta tags, JSON-LD, <time>, embedded JSON).

    Last resort (not on homepages, whose first date is just their newest item): the first date written
    out in the text, labelled "dated" because it is a guess.
    """
    guessed = False
    out = {}
    for key, patterns in _META_RE.items():
        for pat in patterns:
            m = re.search(pat, html_text, re.I)
            if m and day(m.group(1)):
                out[key] = day(m.group(1))
                break
    if "published" not in out:
        m = re.search(r'<time[^>]*datetime=["\'](\d{4}-\d{2}-\d{2})', html_text, re.I)
        if m:
            out["published"] = m.group(1)
    if "published" not in out:  # page builders (Framer, Next.js, ...) keep it in embedded JSON
        m = re.search(r'"(?:date|publishedAt|published_at|publishDate|datePublished)"\s*[,:]\s*"(\d{4}-\d{2}-\d{2})', html_text)
        if m:
            out["published"] = m.group(1)
    if "published" not in out and not out and not homepage:  # last resort: first date in the page text
        m = _TEXT_DATE_RE.search(re.sub(r"<[^>]+>", " ", html_text))
        if m:
            out["published"] = text_date(m)
            guessed = True
    if not out:
        return {}
    same = out.get("updated") == out.get("published")
    out["kind"] = "web page"
    out["label"] = join(f"{'dated' if guessed else 'published'} {out['published']}" if out.get("published") else None,
                        f"updated {out['updated']}" if out.get("updated") and not same else None)
    return out


# ---------------------------------------------------------------- dispatch

_ISBN_RE = re.compile(r"/(?:dp|gp/product|isbn)/(\d{9}[\dX]|\d{13})\b", re.I)


def date_info(url: str, youtube: dict[str, str] | None = None) -> dict:
    """Dates for one URL, dispatched by host; {} when nothing is found. `youtube` holds pre-fetched video dates."""
    u = urllib.parse.urlsplit(url)
    host = u.netloc.lower().removeprefix("www.")
    path = u.path
    try:
        vid = youtube_id(url)
        if vid:
            d = (youtube or {}).get(vid) or youtube_dates([vid]).get(vid)
            return {"kind": "youtube video", "published": d, "label": f"published {d}"} if d else {}
        m = re.match(r"/([^/]+)/([^/#?]+)", path)
        if host == "github.com" and m and m.group(1) not in ("orgs", "topics", "search", "features", "about"):
            return github(m.group(1), m.group(2).removesuffix(".git"))
        m = re.match(r"/(?:abs|pdf|html)/([\w.\-/]+?)(?:v\d+)?(?:\.pdf)?$", path)
        if host.endswith("arxiv.org") and m:
            return arxiv(m.group(1))
        if host in ("doi.org", "dx.doi.org"):
            return crossref(path.lstrip("/"))
        m = _ISBN_RE.search(path)
        if m and ("amazon." in host or "openlibrary" in host or "goodreads" in host or "books.google" in host):
            return book(m.group(1))
        m = re.match(r"(\w+)\.(?:m\.)?wikipedia\.org", host)
        if m and path.startswith("/wiki/"):
            return wikipedia(m.group(1), urllib.parse.unquote(path[len("/wiki/"):]))
        m = re.match(r"/project/([^/]+)", path)
        if host == "pypi.org" and m:
            return pypi(m.group(1))
        m = re.match(r"/package/((?:@[^/]+/)?[^/]+)", path)
        if host == "npmjs.com" and m:
            return npm(urllib.parse.unquote(m.group(1)))
        m = re.match(r"/(datasets|spaces)?/?([^/]+/[^/#?]+)", path)
        if host == "huggingface.co" and m and not path.startswith(("/docs", "/blog", "/papers")):
            return huggingface(m.group(1) or "models", m.group(2))
        return page_dates(get(url, raw=True), homepage=path.strip("/") == "")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, subprocess.TimeoutExpired):
        return {}


def main(argv=None) -> int:
    urls = (argv if argv is not None else sys.argv[1:])
    if not urls or urls[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    yt = youtube_dates([v for v in map(youtube_id, urls) if v])
    print(json.dumps({u: date_info(u, yt) for u in urls}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

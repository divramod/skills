#!/usr/bin/env python3
"""Prepare a document (a local file or a document URL) for summarizing.

1. A URL is downloaded first (a local file is read in place). The file's sha256 is the id: the same document is
   reused wherever it lies or however it is named (--refresh converts it again). A path or URL that was
   prepared before with other content is a new version: it is converted into the same folder, and
   `extras.versions` keeps the earlier hashes with their dates.
2. The file is copied into the folder as original.<ext> (the page links to it).
3. convert.py turns it into markdown: markitdown, else pdftotext (PDF) or pandoc; a PDF is split into pages.
4. content.md: a header (title, author, date, pages, converter, the original), then the text. A PDF's paragraphs
   each start with a page anchor `[p. n](original.pdf#page=n)` (opens the copy at that page); a slide deck has
   `## Slide n` headings; other documents keep their own headings.
5. metadata.json: the shared contract fields (extras: kind, original_path, original_file, pages, sha256, size,
   converter, versions, aliases, attempts).
Folder: <root>/documents/<parent-folder>/<file-stem>/ (a URL: documents/<host>/<file-stem>/). Prints the source envelope.

Usage: prepare.py <path|url> [--refresh]
Requires: uvx (markitdown); pdftotext and pandoc as fallbacks.
"""
from __future__ import annotations

import argparse
import email.message
import hashlib
import json
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps
sys.path.insert(0, str(Path(__file__).resolve().parent))  # convert.py

from _common import SkillError, envelope, find_by_id, log, read_json, run_main, unique_dir, update_json
from convert import Document, convert
from route import DOC_EXT, route

BIG = 50 * 1024 * 1024  # warn above this
MAX_DOWNLOAD = 500 * 1024 * 1024
TIMEOUT = 120


# ---------------------------------------------------------------- input


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, into: Path) -> Path:
    """The document at url, saved under its own file name in `into`."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (tell-me)"})
    log(f"downloading {url}")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            name = file_name(url, r.headers)
            size = int(r.headers.get("Content-Length") or 0)
            if size > MAX_DOWNLOAD:
                raise SkillError(f"{url} is {size // 2**20} MB, more than {MAX_DOWNLOAD // 2**20} MB")
            target = into / name
            with open(target, "wb") as f:
                shutil.copyfileobj(r, f, 1 << 20)
    except urllib.error.HTTPError as e:
        raise SkillError(f"{url} answered HTTP {e.code}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise SkillError(f"could not download {url}: {getattr(e, 'reason', e)}")
    return target


def file_name(url: str, headers: email.message.Message) -> str:
    """The download's file name: Content-Disposition, else the URL's last segment, with an extension that
    matches the content type when the URL has none (arxiv.org/pdf/<id>)."""
    msg = email.message.Message()
    msg["content-disposition"] = headers.get("Content-Disposition") or ""
    name = msg.get_filename() or urllib.parse.unquote(urllib.parse.urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1])
    name = re.sub(r"[^\w.\- ]+", "_", Path(name).name).strip(" .") or "document"
    ctype = headers.get_content_type() if hasattr(headers, "get_content_type") else ""
    ext = {"application/pdf": ".pdf", "application/epub+zip": ".epub", "text/html": ".html", "text/plain": ".txt",
           "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
           "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx"}.get(ctype)
    if ext and Path(name).suffix.lower() not in DOC_EXT:  # no extension, or a dot in an id (1706.03762)
        name += ext
    return name


# ---------------------------------------------------------------- content


def page_body(pages: list[str], original: str) -> str:
    """Every paragraph of every page, starting with its page anchor."""
    out = []
    for n, page in enumerate(pages, 1):
        anchor = f"[p. {n}]({original}#page={n})"
        paragraphs = [p for p in page.split("\n\n") if p.strip()]
        out += [f"{anchor} {p}" for p in paragraphs] or [f"{anchor} *(no text on this page)*"]
    return "\n\n".join(out)


def demote(markdown: str, levels: int = 2) -> str:
    """The document's headings pushed below `## Document` (# -> ###), fenced code left alone."""
    out, fence = [], None
    for line in markdown.splitlines():
        if m := re.match(r"\s{0,3}(`{3,}|~{3,})", line):
            if fence is None:
                fence = m.group(1)
            elif m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
        elif fence is None and (m := re.match(r"(#{1,6})(\s)", line)):
            line = "#" * min(6, len(m.group(1)) + levels) + line[len(m.group(1)):]
        out.append(line)
    return "\n".join(out)


def strip_front_matter(text: str) -> str:
    return re.sub(r"\A---\n.*?\n---\n+", "", text, flags=re.S)


def render_content(meta: dict, extras: dict, doc: Document) -> str:
    original = extras["original_file"]
    rows = [f"# {meta['title']}", "", f"- original: [{original}]({original})"]
    source = meta["url"] if not meta["url"].startswith("file://") else extras.get("original_path")
    for label, value in (("source", source), ("author", meta.get("author")), ("date", meta.get("published")),
                         ("pages", extras.get("pages")), ("converter", extras.get("converter")),
                         ("words", meta.get("word_count"))):
        if value:
            rows.append(f"- {label}: {value}")
    body = page_body(doc.pages, original) if doc.pages else demote(strip_front_matter(doc.markdown).strip())
    rows += ["", "## Document", "", body or "*No text could be extracted.*", ""]
    return "\n".join(rows)


def title_of(doc: Document, path: Path) -> str:
    title = " ".join((doc.title or "").split())
    if title and not re.fullmatch(r"(untitled|microsoft word - .*|document\d*|slide \d+)", title, re.I):
        return title
    return path.stem.replace("_", " ").replace("-", " ").strip() or path.name


# ---------------------------------------------------------------- main


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="a local document path, file:// URL or document URL")
    ap.add_argument("--refresh", action="store_true", help="convert again even if it was prepared before")
    args = ap.parse_args(argv)

    remote = args.input.startswith(("http://", "https://"))
    r = {"url": args.input} if remote else route(args.input)
    if not remote and r["source"] != "file":
        raise SkillError(f"{args.input} is a {r['source']} input, not a document")
    with tempfile.TemporaryDirectory(prefix="tell-me-file-") as tmp:
        path = download(r["url"], Path(tmp)) if remote else Path(r["path"])
        return prepare(path, r["url"] if remote else None, args.refresh)


def prepare(path: Path, url: str | None, refresh: bool) -> int:
    size = path.stat().st_size
    if size > BIG:
        log(f"{path.name} is {size // 2**20} MB: converting it can take a while")
    digest = sha256(path)
    where = url or str(path)  # the path or URL this run came from
    existing = find_by_id("file", digest)
    if existing and (existing / "content.md").exists() and not refresh:
        log(f"reusing: {existing} (same content; pass --refresh to convert again)")
        meta = read_json(existing / "metadata.json")
        if where not in ((meta.get("extras") or {}).get("aliases") or []):  # found under another name
            extras = meta.get("extras") or {}
            meta = update_json(existing / "metadata.json", {"extras": extras | {
                "aliases": sorted({*(extras.get("aliases") or []), where})}})
        return print_envelope(existing, meta, reused=True)

    earlier = existing or find_by_id("file", where)  # the same path or URL, maybe with other content
    old = read_json(earlier / "metadata.json") if earlier else {}
    old_extras = old.get("extras") or {}
    versions = list(old_extras.get("versions") or [])
    changed = bool(old.get("id")) and old.get("id") != digest
    if changed:
        versions.append({"sha256": old["id"], "prepared": old.get("fetched")})
        log(f"{where} changed since {old.get('fetched')}: converting the new version into the same folder")

    doc = convert(path)
    ext = path.suffix.lower() or ".bin"
    original = f"original{ext}"
    extras = {k: v for k, v in {
        "kind": ext.lstrip("."), "original_path": None if url else str(path), "file_name": path.name if url else None,
        "original_file": original,
        "pages": len(doc.pages) if doc.pages else None, "sha256": digest, "size": size, "converter": doc.converter,
        "versions": versions or None, "aliases": sorted({*(old_extras.get("aliases") or []), where}),
        "attempts": doc.attempts or None,
    }.items() if v is not None}
    meta = {
        "source": "file", "id": digest, "url": url or path.resolve().as_uri(), "title": title_of(doc, path),
        "author": doc.author, "published": doc.published, "fetched": datetime.now().isoformat(timespec="seconds"),
        "site": urllib.parse.urlsplit(url).hostname if url else "local", "word_count": 0, "duration": None,
        "extractor": doc.converter, "content_file": "content.md", "extras": extras,
    }
    meta["word_count"] = len(render_content(meta, extras, doc).split())
    folder = earlier or unique_dir(meta)
    folder.mkdir(parents=True, exist_ok=True)
    log(f"{'refreshing' if earlier else 'folder'}: {folder}")
    for stale in folder.glob("original.*"):
        if stale.name != original:
            stale.unlink()
    shutil.copy2(path, folder / original)
    (folder / "content.md").write_text(render_content(meta, extras, doc), encoding="utf-8")
    meta = update_json(folder / "metadata.json", meta | {"prepared_at": old.get("prepared_at") or meta["fetched"]})
    return print_envelope(folder, meta, reused=bool(earlier), changed=changed)


def print_envelope(folder: Path, meta: dict, reused: bool, changed: bool = False) -> int:
    extras = meta.get("extras") or {}
    print(json.dumps(envelope(folder, meta, "document", reused=reused, changed=changed or None,
                              doc_kind=extras.get("kind"), pages=extras.get("pages"),
                              original=str(folder / extras["original_file"]) if extras.get("original_file") else None,
                              converter=extras.get("converter"), versions=extras.get("versions"),
                              attempts=extras.get("attempts")),
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    run_main(main)

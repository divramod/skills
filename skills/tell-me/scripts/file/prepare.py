#!/usr/bin/env python3
"""Prepare a document (a local file or a document URL) for summarizing.

1. A URL is downloaded first (a local file is read in place; a server that sends an HTML page for a PDF, e.g. a
   captcha, is an error). The file's sha256 is the id: the same document is reused wherever it lies or however it
   is named (--refresh converts it again).
2. A path or URL prepared before with other content is a new version when there is evidence it is the same
   document (the same title, or mostly the same words; --refresh counts as evidence): it is converted into the same
   folder, the earlier original and summary are kept as original.<sha8>.<ext> and summary.<sha8>.md/.html (so
   summary_exists is false), `extras.versions` lists the earlier hashes, and the path now belongs to this version
   alone (aliases). Without evidence it is another document saved under the same name: a new folder.
3. The file is copied into the folder as original.<ext> (the page links to it).
4. convert.py turns it into markdown: pdftotext for PDFs (markitdown as fallback), markitdown / pandoc / textutil for
   the rest; a PDF is split into pages.
5. content.md: a header (title, author, date, pages, converter, the original), then the text. A PDF's paragraphs
   each start with a page anchor `[p. n](original.pdf#page=n)` (opens the copy at that page); a slide deck has
   `## Slide n` headings; plain text (.txt, .csv, .json, ...) sits in a code fence; other documents keep their own
   headings.
6. metadata.json: the shared contract fields (extras: kind, original_path, original_file, pages, sha256, size,
   converter, versions, aliases, attempts).
Folder: <root>/documents/<parent-folder>/<file-stem>/ (a URL: documents/<host>/<file-stem>/). Prints the source envelope.

Usage: prepare.py <path|url> [--refresh]
Requires: pdftotext (poppler) and uvx (markitdown); pandoc and textutil (macOS) as fallbacks.
"""
from __future__ import annotations

import argparse
import email.message
import hashlib
import json
import os
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
from route import DOC_EXT, REMOTE_DOC_EXT, route

BIG = 50 * 1024 * 1024  # warn above this
MAX_DOWNLOAD = 500 * 1024 * 1024
TIMEOUT = 120
HEAD = 4096  # the first bytes of a download: enough to tell a PDF or an HTML page
CONTENT_EXT = {"application/pdf": ".pdf", "application/epub+zip": ".epub", "text/html": ".html", "text/plain": ".txt",
               "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
               "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx"}
SAME_WORDS = 0.5  # share of words two versions of one document have in common (at least)


# ---------------------------------------------------------------- input


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, into: Path) -> Path:
    """The document at url, saved under its own file name in `into`. At most MAX_DOWNLOAD bytes (counted while
    streaming: a server may send no Content-Length or a wrong one)."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (tell-me)"})
    log(f"downloading {url}")
    too_big = f"{url} is more than {MAX_DOWNLOAD // 2**20} MB"
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            if int(r.headers.get("Content-Length") or 0) > MAX_DOWNLOAD:
                raise SkillError(too_big)
            head = r.read(HEAD)
            name = file_name(url, r.headers, head)
            check_payload(url, name, r.headers.get_content_type(), head)
            target, total = into / name, len(head)
            with open(target, "wb") as f:
                f.write(head)
                while chunk := r.read(1 << 20):
                    total += len(chunk)
                    if total > MAX_DOWNLOAD:
                        raise SkillError(too_big)
                    f.write(chunk)
    except urllib.error.HTTPError as e:
        raise SkillError(f"{url} answered HTTP {e.code}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise SkillError(f"could not download {url}: {getattr(e, 'reason', e)}")
    return target


def is_pdf(head: bytes) -> bool:
    return b"%PDF-" in head[:1024]  # the header may follow a few bytes of junk


def looks_html(head: bytes) -> bool:
    start = head[:512].removeprefix(b"\xef\xbb\xbf")
    return re.match(rb"\s*(<!doctype html|<html|<head|<body|<!--)", start, re.I) is not None


def file_name(url: str, headers: email.message.Message, head: bytes = b"") -> str:
    """The download's file name: Content-Disposition, else the URL's last segment, with an extension that
    matches the content (a PDF's magic bytes, else the content type) when the name has none that we read
    (arxiv.org/pdf/<id>, an application/octet-stream download)."""
    msg = email.message.Message()
    msg["content-disposition"] = headers.get("Content-Disposition") or ""
    name = msg.get_filename() or urllib.parse.unquote(urllib.parse.urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1])
    name = re.sub(r"[^\w.\- ]+", "_", Path(name).name).strip(" .") or "document"
    ctype = headers.get_content_type() if hasattr(headers, "get_content_type") else ""
    ext = ".pdf" if is_pdf(head) else CONTENT_EXT.get(ctype)
    if ext and Path(name).suffix.lower() not in DOC_EXT:  # no extension, or a dot in an id (1706.03762)
        name += ext
    return name


def check_payload(url: str, name: str, ctype: str, head: bytes) -> None:
    """SkillError when the server sent something other than the document: an HTML page (a captcha, a login or
    cookie wall) for a .pdf/.docx/... URL, or a ".pdf" that is no PDF."""
    suffix = Path(name).suffix.lower()
    if suffix in REMOTE_DOC_EXT and (ctype == "text/html" or looks_html(head)) and not is_pdf(head):
        raise SkillError(f"{url} sent an HTML page ({ctype}), not the {suffix} document: probably a captcha, login "
                         f"or cookie page. Download it in a browser and pass the file's path")
    if suffix == ".pdf" and head and not is_pdf(head):
        raise SkillError(f"{url} is not a PDF (content type {ctype}, it starts with {head[:16]!r}): download it in "
                         f"a browser and pass the file's path")


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


def fenced(text: str, language: str) -> str:
    """Plain text in a code fence longer than any backtick run inside it."""
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}{language}\n{text.rstrip()}\n{fence}"


def render_content(meta: dict, extras: dict, doc: Document) -> str:
    original = extras["original_file"]
    rows = [f"# {meta['title']}", "", f"- original: [{original}]({original})"]
    source = meta["url"] if not meta["url"].startswith("file://") else extras.get("original_path")
    for label, value in (("source", source), ("author", meta.get("author")), ("date", meta.get("published")),
                         ("pages", extras.get("pages")), ("converter", extras.get("converter"))):
        if value:
            rows.append(f"- {label}: {value}")
    if doc.pages:
        body = page_body(doc.pages, original)
    elif doc.language:
        body = fenced(doc.markdown, doc.language) if doc.markdown.strip() else ""
    else:
        body = demote(strip_front_matter(doc.markdown).strip())
    rows += ["", "## Document", "", body or "*No text could be extracted.*", ""]
    return "\n".join(rows)


GENERIC_TITLE_RE = re.compile(r"(untitled|microsoft word - .*|document\d*|slide \d+)", re.I)


def own_title(doc: Document) -> str | None:
    """The document's own title (its properties or first heading), unless it is a placeholder."""
    title = " ".join((doc.title or "").split())
    return title if title and not GENERIC_TITLE_RE.fullmatch(title) else None


def title_of(doc: Document, path: Path) -> str:
    return own_title(doc) or path.stem.replace("_", " ").replace("-", " ").strip() or path.name


def word_set(text: str) -> set[str]:
    return set(re.findall(r"\w+", re.sub(r"\[p\. \d+\]\([^)]*\)", " ", text).lower()))


def same_document(folder: Path, old: dict, doc: Document) -> bool:
    """Evidence that new content at a path or URL prepared before is a new version of the document there, not
    another document saved under the same name (~/Downloads/paper.pdf): the same title (the document's own, not a
    file name), or at least SAME_WORDS of their distinct words in common."""
    title = own_title(doc)
    if title and title.casefold() == str(old.get("title") or "").casefold():
        return True
    try:
        before = (folder / (old.get("content_file") or "content.md")).read_text(encoding="utf-8")
    except OSError:
        return False
    before = word_set(before.split("\n## Document\n", 1)[-1])
    now = word_set(doc.markdown)
    return bool(before and now) and len(before & now) / len(before | now) >= SAME_WORDS


# ---------------------------------------------------------------- main


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="a local document path, file:// URL or document URL")
    ap.add_argument("--refresh", action="store_true",
                    help="convert again even if it was prepared before; new content at a known path is a new version")
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
    doc = convert(path)
    changed = bool(old.get("id")) and old.get("id") != digest
    if changed and not refresh and not same_document(earlier, old, doc):
        log(f"{where} now holds another document than {earlier} ({old.get('title')!r}): preparing it in a new "
            f"folder (pass --refresh to treat it as a new version of that one)")
        forget_alias(earlier, old, where)
        earlier, old, changed = None, {}, False
    old_extras = old.get("extras") or {}
    versions = list(old_extras.get("versions") or [])
    ext = path.suffix.lower() or ".bin"
    original = f"original{ext}"
    extras = {k: v for k, v in {
        "kind": ext.lstrip("."), "original_path": None if url else str(path), "file_name": path.name if url else None,
        "original_file": original,
        "pages": len(doc.pages) if doc.pages else None, "sha256": digest, "size": size, "converter": doc.converter,
        "versions": None, "attempts": doc.attempts or None,
        # a new version: the path now belongs to it alone (other names had the earlier content)
        "aliases": [where] if changed else sorted({*(old_extras.get("aliases") or []), where}),
    }.items() if v is not None}
    meta = {
        "source": "file", "id": digest, "url": url or path.resolve().as_uri(), "title": title_of(doc, path),
        "author": doc.author, "published": doc.published, "fetched": datetime.now().isoformat(timespec="seconds"),
        "site": urllib.parse.urlsplit(url).hostname if url else "local", "word_count": 0, "duration": None,
        "extractor": doc.converter, "content_file": "content.md", "extras": extras,
    }
    folder = earlier or unique_dir(meta)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / original
    in_place = target.exists() and os.path.samefile(path, target)  # the library's own copy passed back in
    if changed:
        log(f"{where} changed since {old.get('fetched')}: converting the new version into {folder}")
        versions.append(keep_version(folder, old, path))
    else:
        log(f"{'refreshing' if earlier else 'folder'}: {folder}")
    if versions:
        extras["versions"] = versions
    for stale in folder.glob("original.*"):  # the copy under another extension (not a kept version)
        if stale.name != original and re.fullmatch(r"original\.[^.]+", stale.name):
            stale.unlink()
    if not in_place:
        shutil.copy2(path, target)
    content = render_content(meta, extras, doc)
    meta["word_count"] = len(content.split())
    (folder / "content.md").write_text(content, encoding="utf-8")
    meta = update_json(folder / "metadata.json", meta | {"prepared_at": old.get("prepared_at") or meta["fetched"]},
                       drop=("summary",) if changed else ())
    return print_envelope(folder, meta, reused=bool(earlier), changed=changed)


def keep_version(folder: Path, old: dict, path: Path) -> dict:
    """Move the earlier version's original and summary aside (original.<sha8>.<ext>, summary.<sha8>.md/.html;
    their page links follow the original) and return its `versions` entry."""
    short = str(old["id"])[:8]
    entry = {"sha256": old["id"], "prepared": old.get("fetched")}
    renamed = {}
    before = (old.get("extras") or {}).get("original_file")
    if before and (folder / before).exists() and not os.path.samefile(path, folder / before):
        kept = f"original.{short}{Path(before).suffix}"
        (folder / before).rename(folder / kept)
        entry["original_file"] = renamed[before] = kept
    for ext in (".md", ".html"):
        summary = folder / f"summary{ext}"
        if summary.exists():
            kept = folder / f"summary.{short}{ext}"
            text = summary.read_text(encoding="utf-8")
            for a, b in renamed.items():
                text = text.replace(a, b)
            kept.write_text(text, encoding="utf-8")
            summary.unlink()
            entry.setdefault("summary_file", kept.name)
    if old.get("summary"):
        entry["summary"] = old["summary"]
    return entry


def forget_alias(folder: Path, old: dict, where: str) -> None:
    """The path or URL now names another document: the earlier folder no longer answers to it."""
    extras = old.get("extras") or {}
    if where in (extras.get("aliases") or []):
        update_json(folder / "metadata.json",
                    {"extras": extras | {"aliases": [a for a in extras["aliases"] if a != where]}})


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

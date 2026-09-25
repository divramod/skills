#!/usr/bin/env python3
"""Convert a document to markdown for the file source, and read its title, author and date.

Converters, first that works wins (every failure is noted in `attempts`):
  - text formats (.md, .txt, .rst, .org, .tex, .csv, .json, .xml): read as they are
  - .pdf: markitdown (its text keeps the page breaks), else `pdftotext` (poppler); split into pages. The text is
    cleaned: runs of one-letter lines (a rotated margin stamp such as arXiv's) are dropped, lines are joined into
    paragraphs and words hyphenated at a line end are joined
  - everything else (.docx, .pptx, .xlsx, .epub, .html, .odt, …): markitdown, else `pandoc -t gfm` for the
    formats pandoc reads. A .pptx gets one `## Slide n` heading per slide
markitdown runs as `uvx --from 'markitdown[all]==<pinned>' markitdown <file>` (the first run downloads its
dependencies, about a minute).
Properties: the document's own (docx/pptx/xlsx core.xml, the epub's OPF, pdfinfo, html <title>, markdown front
matter or first heading); a PDF without a title gets the largest line of its first page (pdftotext -bbox).

Usage: convert.py <file>   (prints {converter, pages, title, author, published, attempts} and the markdown)
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

from _common import MissingTool, SkillError, install_script, log, run_main

MARKITDOWN = ["uvx", "--from", "markitdown[all]==0.1.5", "markitdown"]
TIMEOUT = 900  # the first markitdown run installs ~50 packages
TEXT_EXT = {".md", ".markdown", ".txt", ".rst", ".org", ".tex", ".csv", ".json", ".xml"}
PANDOC_EXT = {".docx", ".epub", ".odt", ".rtf", ".html", ".htm", ".ipynb", ".tex", ".rst", ".org"}
OFFICE_EXT = {".docx", ".pptx", ".xlsx"}
MIN_WORDS = 20  # less than this from a converter: treat as a failure (a scanned PDF has no text layer)


@dataclass
class Document:
    markdown: str  # the whole text; for a PDF the pages joined
    converter: str
    pages: list[str] | None = None  # a PDF's text per page
    title: str | None = None
    author: str | None = None
    published: str | None = None  # YYYY-MM-DD
    attempts: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- running tools


def run(cmd: list[str]) -> str:
    """stdout of a converter; SkillError with the end of stderr when it fails."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        raise SkillError(f"{cmd[0]} took longer than {TIMEOUT // 60} minutes")
    if p.returncode != 0:
        raise SkillError((p.stderr.strip().splitlines() or [f"exit {p.returncode}"])[-1][-300:])
    return p.stdout


def words(text: str) -> int:
    return len(text.split())


# ---------------------------------------------------------------- text clean-up


def clean_pdf_page(text: str) -> str:
    """A PDF page's text as paragraphs: drop rotated-stamp debris (runs of 4+ lines of at most 2 characters),
    join the lines of a paragraph, join words hyphenated at a line end."""
    keep, run_ = [], []  # run_: short lines, and the blank lines between them

    def flush():
        if sum(bool(r.strip()) for r in run_) < 4:
            keep.extend(run_)
        else:
            keep.append("")
        run_.clear()
    for line in text.replace("\r", "").split("\n"):
        if 0 < len(line.strip()) <= 2 or (run_ and not line.strip()):
            run_.append(line)
            continue
        flush()
        keep.append(line)
    flush()
    paragraphs, current = [], []
    for line in keep:
        s = line.strip()
        if not s:
            if current:
                paragraphs.append(current)
            current = []
            continue
        current.append(s)
    if current:
        paragraphs.append(current)
    out = []
    for p in paragraphs:
        text = p[0]
        for s in p[1:]:
            if re.search(r"[a-z]-$", text) and re.match(r"[a-z]", s):
                text = text[:-1] + s
            elif re.match(r"^([-•*·▪]|\d+[.)])\s", s):  # a list item starts its own line
                text += "\n" + s
            else:
                text += " " + s
        out.append(re.sub(r"[ \t]+", " ", text))
    return "\n\n".join(out)


def split_pages(text: str) -> list[str]:
    """Form feeds separate the pages in pdfminer's and pdftotext's output; the last one ends the file."""
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    return [clean_pdf_page(p) for p in pages]


def pptx_slides(markdown: str) -> str:
    """markitdown's `<!-- Slide number: n -->` markers as `## Slide n` headings."""
    return re.sub(r"<!-- Slide number: (\d+) -->", r"## Slide \1", markdown)


# ---------------------------------------------------------------- properties


def iso_date(value: str | None) -> str | None:
    """YYYY-MM-DD from an ISO date, a PDF date (D:20240410…) or pdfinfo's `Wed Apr 10 23:11:43 2024 CEST`."""
    if not value:
        return None
    if m := re.search(r"(\d{4})-?(\d{2})-?(\d{2})", value.removeprefix("D:")):
        return "-".join(m.groups())
    try:
        return datetime.strptime(" ".join(value.split()[:5]), "%a %b %d %H:%M:%S %Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def xml_text(root: ElementTree.Element, local: str) -> str | None:
    for el in root.iter():
        if el.tag.rsplit("}", 1)[-1] == local and (el.text or "").strip():
            return el.text.strip()
    return None


def office_props(path: Path) -> dict:
    try:
        with zipfile.ZipFile(path) as z:
            root = ElementTree.fromstring(z.read("docProps/core.xml"))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError, OSError):
        return {}
    return {"title": xml_text(root, "title"), "author": xml_text(root, "creator"),
            "published": iso_date(xml_text(root, "created"))}


def epub_props(path: Path) -> dict:
    try:
        with zipfile.ZipFile(path) as z:
            container = ElementTree.fromstring(z.read("META-INF/container.xml"))
            rootfile = next(el.get("full-path") for el in container.iter() if el.tag.endswith("rootfile"))
            opf = ElementTree.fromstring(z.read(rootfile))
    except (zipfile.BadZipFile, KeyError, StopIteration, ElementTree.ParseError, OSError):
        return {}
    return {"title": xml_text(opf, "title"), "author": xml_text(opf, "creator"),
            "published": iso_date(xml_text(opf, "date"))}


def pdf_props(path: Path) -> dict:
    """pdfinfo's Title/Author/CreationDate (poppler; nothing without it)."""
    if not shutil.which("pdfinfo"):
        return {}
    try:
        out = run(["pdfinfo", str(path)])
    except SkillError:
        return {}
    info = dict(line.split(":", 1) for line in out.splitlines() if ":" in line)
    return {"title": (info.get("Title") or "").strip() or None, "author": (info.get("Author") or "").strip() or None,
            "published": iso_date((info.get("CreationDate") or "").strip())}


_WORD_RE = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>')


def pdf_title_from_layout(bbox_html: str) -> str | None:
    """The largest horizontal line of a page (pdftotext -bbox output): words grouped into lines by top and height,
    rotated words (taller than wide) and one-word lines left out; lines of that size right below are joined."""
    lines: dict[tuple[int, float], list[str]] = defaultdict(list)
    for m in _WORD_RE.finditer(bbox_html):
        x0, y0, x1, y1 = (float(v) for v in m.groups()[:4])
        height = round(y1 - y0, 1)
        if height > (x1 - x0) * 1.5 and len(m.group(5)) > 1:  # rotated
            continue
        lines[(round(y0), height)].append(html.unescape(m.group(5)))
    candidates = sorted(((h, y, ws) for (y, h), ws in lines.items() if len(ws) >= 2), key=lambda c: (-c[0], c[1]))
    if not candidates:
        return None
    size, top, first = candidates[0]
    title = [" ".join(first)]
    for h, y, ws in sorted(candidates, key=lambda c: c[1]):
        if y > top and abs(h - size) < 0.5 and y - top < size * 2.5:
            title.append(" ".join(ws))
            top = y
    return " ".join(title)


def markdown_props(text: str) -> dict:
    front = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    fields = dict(re.findall(r"^(\w+):\s*(.+?)\s*$", front.group(1), re.M)) if front else {}
    heading = re.search(r"^#\s+(.+?)\s*#*\s*$", text, re.M)
    return {"title": fields.get("title", "").strip("'\"") or (heading.group(1) if heading else None),
            "author": fields.get("author", "").strip("'\"") or None, "published": iso_date(fields.get("date"))}


def html_props(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    title = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
    author = re.search(r'<meta\s+name="author"\s+content="([^"]*)"', text, re.I)
    return {"title": html.unescape(" ".join(title.group(1).split())) if title else None,
            "author": html.unescape(author.group(1)) if author else None}


def properties(path: Path, text: str) -> dict:
    ext = path.suffix.lower()
    if ext in OFFICE_EXT:
        props = office_props(path)
    elif ext == ".epub":
        props = epub_props(path)
    elif ext == ".pdf":
        props = pdf_props(path)
        if not props.get("title") and shutil.which("pdftotext"):
            try:
                props["title"] = pdf_title_from_layout(run(["pdftotext", "-f", "1", "-l", "1", "-bbox",
                                                            str(path), "-"]))
            except SkillError:
                pass
    elif ext in (".html", ".htm"):
        props = html_props(path)
    else:
        props = {}
    if not props.get("title"):
        props = markdown_props(text) | {k: v for k, v in props.items() if v}
    return props


# ---------------------------------------------------------------- converting


def markitdown(path: Path, attempts: list[str]) -> str | None:
    if not shutil.which("uvx"):
        attempts.append("markitdown: uvx is missing")
        return None
    log(f"converting {path.name} with markitdown")
    try:
        text = run(MARKITDOWN + [str(path)])
    except SkillError as e:
        attempts.append(f"markitdown: failed ({e})")
        return None
    if words(text) < MIN_WORDS and path.suffix.lower() == ".pdf":
        attempts.append(f"markitdown: only {words(text)} words (a scanned PDF without a text layer?)")
        return None
    return text


def pdftotext(path: Path, attempts: list[str]) -> str | None:
    if not shutil.which("pdftotext"):
        attempts.append("pdftotext: not installed")
        return None
    log(f"converting {path.name} with pdftotext")
    try:
        text = run(["pdftotext", "-enc", "UTF-8", str(path), "-"])
    except SkillError as e:
        attempts.append(f"pdftotext: failed ({e})")
        return None
    if words(text) < MIN_WORDS:
        attempts.append(f"pdftotext: only {words(text)} words (a scanned PDF without a text layer?)")
        return None
    return text


def pandoc(path: Path, attempts: list[str]) -> str | None:
    if path.suffix.lower() not in PANDOC_EXT:
        return None
    if not shutil.which("pandoc"):
        attempts.append("pandoc: not installed")
        return None
    log(f"converting {path.name} with pandoc")
    try:
        return run(["pandoc", str(path), "-t", "gfm", "--wrap=none"])
    except SkillError as e:
        attempts.append(f"pandoc: failed ({e})")
        return None


def no_converter(path: Path, attempts: list[str]) -> SkillError:
    tried = "; ".join(attempts) or "nothing to try"
    if any("uvx is missing" in a for a in attempts):
        return MissingTool(f"uvx (runs markitdown) is missing and no fallback could convert {path.name} ({tried})\n"
                           f"install it: {install_script()}")
    return SkillError(f"could not convert {path.name}: {tried}")


def convert(path: Path) -> Document:
    ext = path.suffix.lower()
    attempts: list[str] = []
    if ext in TEXT_EXT:
        text = path.read_text(encoding="utf-8", errors="replace")
        doc = Document(text, "read")
    elif ext == ".pdf":
        if (text := markitdown(path, attempts)) is not None and "\f" in text:
            doc = Document("", "markitdown")
        elif (fallback := pdftotext(path, attempts)) is not None:
            if text is not None:
                attempts.append("markitdown: no page breaks, pdftotext for the pages")
            text, doc = fallback, Document("", "pdftotext")
        elif text is not None:  # one page, or markitdown without page breaks and no pdftotext
            doc = Document("", "markitdown")
        else:
            raise no_converter(path, attempts)
        doc.pages = split_pages(text)
        doc.markdown = "\n\n".join(doc.pages)
    else:
        text = markitdown(path, attempts)
        converter = "markitdown"
        if text is None or not text.strip():
            if text is not None:
                attempts.append("markitdown: empty output")
            text, converter = pandoc(path, attempts), "pandoc"
        if text is None:
            raise no_converter(path, attempts)
        doc = Document(pptx_slides(text) if ext == ".pptx" else text, converter)
    doc.attempts = attempts
    for a in attempts:
        log(a)
    props = properties(path, doc.markdown)
    doc.title, doc.author, doc.published = props.get("title"), props.get("author"), props.get("published")
    return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", type=Path)
    doc = convert(ap.parse_args(argv).file)
    print(json.dumps({"converter": doc.converter, "pages": len(doc.pages) if doc.pages else None, "title": doc.title,
                      "author": doc.author, "published": doc.published, "attempts": doc.attempts}, indent=2))
    print(doc.markdown)
    return 0


if __name__ == "__main__":
    run_main(main)

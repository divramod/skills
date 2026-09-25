#!/usr/bin/env python3
"""Convert a document to markdown for the file source, and read its title, author and date.

Converters, first that works wins (every failure is noted in `attempts`):
  - markdown (.md, .markdown): read as it is. Plain text (.txt, .csv, .json, .xml, .tex, .org, .rst): read as it
    is and marked for a code fence (`language`). Encodings: UTF-8 (with or without BOM), UTF-16 with a BOM, else
    cp1252 (Windows Latin-1)
  - .pdf: `pdftotext -bbox-layout` (poppler, required: it keeps the reading order of two-column papers), else
    markitdown (its text keeps the page breaks). Split into pages; lines rotated in the margin (arXiv's stamp) are
    dropped, lines are joined into paragraphs, words hyphenated at a line end are joined unless the hyphen belongs
    to a compound (left-to-right, pre-train, task-specific)
  - .rtf: pandoc, else textutil (macOS), else markitdown. .doc: textutil (macOS). .ppt is not supported
  - everything else (.docx, .pptx, .xlsx, .epub, .html, .odt, .ipynb, …): markitdown, else `pandoc -t gfm` for the
    formats pandoc reads. A .pptx gets one `## Slide n` heading per slide
markitdown runs as `uvx --from 'markitdown[all]==<pinned>' markitdown <file>` (the first run downloads its
dependencies, about a minute).
Properties: the document's own (docx/pptx/xlsx core.xml, the epub's OPF, pdfinfo, html <title>, markdown front
matter or first heading); a PDF without a title gets the largest line of its first page.
Exit 2 (missing tool) when the only reason nothing converted is a converter that is not installed.

Usage: convert.py <file>   (prints {converter, pages, title, author, published, attempts} and the markdown)
Requires: pdftotext + pdfinfo (poppler) for PDFs, uvx (markitdown); optional: pandoc, textutil (macOS).
"""
from __future__ import annotations

import argparse
import codecs
import html
import json
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

from _common import MissingTool, SkillError, install_script, log, run_main

MARKITDOWN = ["uvx", "--from", "markitdown[all]==0.1.5", "markitdown"]
TIMEOUT = 900  # the first markitdown run installs ~50 packages
MARKDOWN_EXT = {".md", ".markdown"}
# Plain text: read as it is and shown in a code fence (language per extension).
PLAIN_EXT = {".txt": "text", ".csv": "csv", ".json": "json", ".xml": "xml", ".tex": "latex", ".org": "org",
             ".rst": "rst"}
PANDOC_EXT = {".docx", ".epub", ".odt", ".rtf", ".html", ".htm", ".ipynb"}
TEXTUTIL_EXT = {".doc", ".rtf"}  # macOS textutil reads both; markitdown reads neither
OFFICE_EXT = {".docx", ".pptx", ".xlsx"}
UNSUPPORTED = {".ppt": "PowerPoint 97-2003 (.ppt) files can't be converted: save it as .pptx and pass that"}
MIN_WORDS = 20  # less than this from a converter: treat as a failure (a scanned PDF has no text layer)
# First parts that make a compound rather than a broken word: pre-train, self-attention, non-linear.
COMPOUND_PREFIXES = {"pre", "post", "non", "self", "multi", "semi", "anti", "cross"}


@dataclass
class Document:
    markdown: str  # the whole text; for a PDF the pages joined
    converter: str
    pages: list[str] | None = None  # a PDF's text per page
    title: str | None = None
    author: str | None = None
    published: str | None = None  # YYYY-MM-DD
    attempts: list[str] = field(default_factory=list)
    language: str | None = None  # plain text: shown in a code fence of this language


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


def not_installed(attempts: list[str], converter: str, tool: str) -> None:
    """Note a converter whose tool is missing (no_converter() turns only-missing-tools into exit 2)."""
    attempts.append(f"{converter}: {tool} is not installed")


_NOT_INSTALLED_RE = re.compile(r"[\w-]+: (\S+) is not installed")


def read_text(path: Path) -> str:
    """A text file's content: UTF-8 (a BOM is dropped), UTF-16 with a BOM, else cp1252 (a superset of Latin-1 for
    printable text; bytes cp1252 leaves undefined are read as Latin-1)."""
    data = path.read_bytes()
    if data.startswith(codecs.BOM_UTF8):
        return data[len(codecs.BOM_UTF8):].decode("utf-8", errors="replace")
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16", errors="replace")
    for encoding in ("utf-8", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    return data.decode("latin-1")


# ---------------------------------------------------------------- PDF text clean-up


_TOKEN_RE = re.compile(r"[A-Za-z]+(?:-[A-Za-z]+)*")


def vocabulary(text: str) -> set[str]:
    """The document's lower-case words and hyphenated compounds (with their parts), leaving out the two halves of
    every word broken at a line end: they say nothing about how the word is spelled."""
    text = re.sub(r"\S*-[ \t]*\n\s*\S*", " ", text)
    vocab: set[str] = set()
    for token in _TOKEN_RE.findall(text.lower()):
        vocab.add(token)
        if "-" in token:
            vocab.update(token.split("-"))
    return vocab


def keeps_hyphen(head: str, tail: str, vocab: set[str]) -> bool:
    """Whether `head` (a line ending in "<word>-") and `tail` (the next line) form a compound whose hyphen stays
    (left-to-right, pre-train, task-specific, self-attention), rather than one word broken by the typesetter
    (hyphen-ated). Evidence, first that applies: the first part already holds a hyphen; the document spells the
    word elsewhere with the hyphen (keep) or without it (join); a compound prefix (pre-, self-, ...); both halves
    are words of 3+ letters found elsewhere in the document."""
    prefix = re.search(r"[A-Za-z]+(?:-[A-Za-z]+)*-$", head)
    suffix = re.match(r"[A-Za-z]+", tail)
    if not prefix or not suffix:
        return True
    first, second = prefix.group(0)[:-1].lower(), suffix.group(0).lower()
    if "-" in first:
        return True
    hyphenated, joined = f"{first}-{second}", first + second
    if hyphenated in vocab and joined not in vocab:
        return True
    if joined in vocab:
        return False
    if first in COMPOUND_PREFIXES:
        return True
    return len(first) >= 3 and len(second) >= 3 and first in vocab and second in vocab


def join_line(text: str, line: str, vocab: set[str]) -> str:
    """`line` appended to the paragraph `text`: a hyphenated line end joined (or kept for a compound), a URL
    broken after "/", "-" or "." joined without a space, a list item on its own line."""
    last = text.rsplit(None, 1)[-1] if text.strip() else ""
    in_url = "://" in last or last.lower().startswith("www.")
    if re.match(r"^([-•*·▪]|\d{1,2}[.)])\s", line):  # a list item starts its own line (not "2018. The")
        return text + "\n" + line
    if in_url and (text.endswith(("/", "-")) and re.match(r"[\w#?&=%.~-]", line)
                   or text.endswith(".") and re.match(r"[a-z0-9][\w-]*[./]\S", line)):  # https://blog.\nopenai.com/
        return text + line
    if re.search(r"[A-Za-z]-$", text) and re.match(r"[A-Za-z0-9]", line):
        if not line[0].islower() or keeps_hyphen(text, line, vocab):
            return text + line  # BERT-\nBASE, left-to-\nright
        return text[:-1] + line
    return text + " " + line


def clean_pdf_page(text: str, vocab: set[str] | None = None) -> str:
    """A PDF page's text as paragraphs: drop rotated-stamp debris (runs of 4+ one-character lines, not all digits:
    a column of numbers stays), join the lines of a paragraph (see join_line), and join a paragraph that a column
    break cut (the next one starts in lower case). `vocab`: the whole document's words (vocabulary())."""
    vocab = vocabulary(text) if vocab is None else vocab
    keep, run_ = [], []  # run_: one-character lines, and the blank lines between them

    def flush():
        chars = [r.strip() for r in run_ if r.strip()]
        if len(chars) < 4 or all(c.isdigit() for c in chars):
            keep.extend(run_)
        else:
            keep.append("")
        run_.clear()
    for line in text.replace("\r", "").split("\n"):
        if len(line.strip()) == 1 or (run_ and not line.strip()):
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
    out: list[str] = []
    for p in paragraphs:
        text = p[0]
        for s in p[1:]:
            text = join_line(text, s, vocab)
        text = re.sub(r"[ \t]+", " ", text)
        if out and re.match(r"[a-z]", text) and re.search(r"[a-z,-]$", out[-1]) and words(out[-1]) >= 10:
            # a paragraph cut mid-sentence by a column break (not a heading: those are short)
            out[-1] = join_line(out[-1], text, vocab)
        elif out and re.fullmatch(r"\d{1,2}(\.\d{1,2})*", out[-1]) and words(text) <= 12 \
                and not re.search(r"[.!?]$", text):  # a section number and its heading: "2.1 Related Work"
            out[-1] += " " + text
        else:
            out.append(text)
    return "\n\n".join(out)


def split_pages(text: str) -> list[str]:
    """Form feeds separate the pages in pdfminer's (markitdown's) output; the last one ends the file."""
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    vocab = vocabulary("\n".join(pages))
    return [clean_pdf_page(p, vocab) for p in pages]


_PAGE_RE = re.compile(r"<page\b[^>]*>(.*?)</page>", re.S)
_BLOCK_RE = re.compile(r"<block\b[^>]*>(.*?)</block>", re.S)
_BOX = r'xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)"'
_LINE_RE = re.compile(rf"<line {_BOX}>(.*?)</line>", re.S)
_WORD_RE = re.compile(rf"<word {_BOX}>([^<]*)</word>")


def layout_pages(bbox_layout: str) -> list[str]:
    """The text of each page of `pdftotext -bbox-layout` output, in poppler's reading order (column by column):
    lines rotated in the margin left out, a paragraph per block, split further where a line is indented, follows a
    gap or follows a short line that ends a sentence. Hyphens stay as printed (plain pdftotext drops them)."""
    pages = []
    for page in _PAGE_RE.findall(bbox_layout):
        paragraphs: list[list[str]] = []
        for block in _BLOCK_RE.findall(page):
            lines = []
            for m in _LINE_RE.finditer(block):
                x0, y0, x1, y1 = (float(v) for v in m.groups()[:4])
                text = " ".join(html.unescape(w.group(5)) for w in _WORD_RE.finditer(m.group(5))).strip()
                if not text or (y1 - y0 > (x1 - x0) * 1.5 and len(text) >= 3):  # rotated: a margin stamp
                    continue
                lines.append((x0, y0, x1, y1, text))
            if not lines:
                continue
            left, right = min(l[0] for l in lines), max(l[2] for l in lines)
            current = [lines[0][4]]
            for prev, line in zip(lines, lines[1:]):
                height = line[3] - line[1]
                ends_sentence = re.search(r"[.!?:]['\"”’)]?$", prev[4])
                new = (line[1] - prev[3] > height * 0.8  # a gap
                       or (ends_sentence and (line[0] > left + height * 0.8  # an indented first line
                                              or prev[2] < right - (right - left) * 0.15)))  # a short last line
                if new:
                    paragraphs.append(current)
                    current = []
                current.append(line[4])
            paragraphs.append(current)
        pages.append("\n\n".join("\n".join(p) for p in paragraphs))
    return pages


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


def pdf_title_from_layout(bbox_html: str) -> str | None:
    """The largest horizontal line of a page (pdftotext -bbox or -bbox-layout output): words grouped into lines by
    top and height (within a small tolerance: a title line mixes fonts), rotated words and one-word lines left
    out; lines of that size right below are joined. Rotated: taller than wide with 3+ characters (a short upright
    word such as "to" or "1" in a large font is taller than wide too)."""
    lines: list[list] = []  # [top, height, words]
    for m in _WORD_RE.finditer(bbox_html):
        x0, y0, x1, y1 = (float(v) for v in m.groups()[:4])
        word, height = html.unescape(m.group(5)), y1 - y0
        if height > (x1 - x0) * 1.5 and len(word) >= 3:  # rotated
            continue
        for line in lines:
            if abs(line[0] - y0) < 2 and abs(line[1] - height) < 0.5:
                line[2].append(word)
                break
        else:
            lines.append([y0, height, [word]])
    candidates = sorted(((h, y, ws) for y, h, ws in lines if len(ws) >= 2), key=lambda c: c[1])
    if not candidates:
        return None
    largest = max(h for h, _, _ in candidates)
    size, top, first = next(c for c in candidates if c[0] > largest - 0.5)  # the topmost line of that size
    title = [" ".join(first)]
    for h, y, ws in candidates:
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
    text = read_text(path)
    title = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
    author = re.search(r'<meta\s+name="author"\s+content="([^"]*)"', text, re.I)
    return {"title": html.unescape(" ".join(title.group(1).split())) if title else None,
            "author": html.unescape(author.group(1)) if author else None}


def properties(path: Path, text: str, first_page_layout: str | None = None) -> dict:
    """Title, author, date. `first_page_layout`: pdftotext's bbox output of a PDF's first page, when at hand."""
    ext = path.suffix.lower()
    if ext in PLAIN_EXT:
        return {}  # no properties; a "# " line in a .txt or .tex is no heading
    if ext in OFFICE_EXT:
        props = office_props(path)
    elif ext == ".epub":
        props = epub_props(path)
    elif ext == ".pdf":
        props = pdf_props(path)
        if not props.get("title"):
            if first_page_layout is None and shutil.which("pdftotext"):
                try:
                    first_page_layout = run(["pdftotext", "-f", "1", "-l", "1", "-bbox", str(path), "-"])
                except SkillError:
                    pass
            props["title"] = pdf_title_from_layout(first_page_layout or "")
    elif ext in (".html", ".htm"):
        props = html_props(path)
    else:
        props = {}
    if not props.get("title"):
        props = markdown_props(text) | {k: v for k, v in props.items() if v}
    return props


# ---------------------------------------------------------------- converters


def markitdown(path: Path, attempts: list[str]) -> str | None:
    if not shutil.which("uvx"):
        not_installed(attempts, "markitdown", "uvx")
        return None
    log(f"converting {path.name} with markitdown")
    try:
        text = run(MARKITDOWN + [str(path)])
    except SkillError as e:
        attempts.append(f"markitdown: failed ({e})")
        return None
    if path.suffix.lower() == ".pdf" and words(text) < MIN_WORDS:
        attempts.append(f"markitdown: only {words(text)} words (a scanned PDF without a text layer?)")
        return None
    return text


def pdftotext(path: Path, attempts: list[str]) -> tuple[list[str], str] | None:
    """(the raw text of each page, the first page's layout) from `pdftotext -bbox-layout`."""
    if not shutil.which("pdftotext"):
        not_installed(attempts, "pdftotext", "pdftotext")
        return None
    log(f"converting {path.name} with pdftotext")
    try:
        layout = run(["pdftotext", "-enc", "UTF-8", "-bbox-layout", str(path), "-"])
    except SkillError as e:
        attempts.append(f"pdftotext: failed ({e})")
        return None
    pages = layout_pages(layout)
    if (n := sum(words(p) for p in pages)) < MIN_WORDS:
        attempts.append(f"pdftotext: only {n} words (a scanned PDF without a text layer?)")
        return None
    first = _PAGE_RE.search(layout)
    return pages, first.group(0) if first else ""


def pandoc(path: Path, attempts: list[str]) -> str | None:
    if path.suffix.lower() not in PANDOC_EXT:
        return None
    if not shutil.which("pandoc"):
        not_installed(attempts, "pandoc", "pandoc")
        return None
    log(f"converting {path.name} with pandoc")
    try:
        return run(["pandoc", str(path), "-t", "gfm", "--wrap=none"])
    except SkillError as e:
        attempts.append(f"pandoc: failed ({e})")
        return None


def textutil(path: Path, attempts: list[str]) -> str | None:
    """macOS's textutil (Word 97-2003 .doc, .rtf) as plain text; other systems don't have it."""
    if path.suffix.lower() not in TEXTUTIL_EXT:
        return None
    if not shutil.which("textutil"):
        attempts.append("textutil: not available (macOS only)")
        return None
    log(f"converting {path.name} with textutil")
    try:
        return run(["textutil", "-convert", "txt", "-stdout", str(path)])
    except SkillError as e:
        attempts.append(f"textutil: failed ({e})")
        return None


def usable(name: str, text: str | None, attempts: list[str]) -> bool:
    """Whether a converter's output is text (not empty, not the raw RTF markitdown passes through)."""
    if text is None:
        return False
    if not text.strip():
        attempts.append(f"{name}: empty output")
        return False
    if text.lstrip().startswith("{\\rtf"):
        attempts.append(f"{name}: returned the raw RTF")
        return False
    return True


def no_converter(path: Path, attempts: list[str]) -> SkillError:
    """MissingTool (exit 2) when every attempt failed only because its tool is not installed, else SkillError."""
    tried = "; ".join(attempts) or "nothing to try"
    missing = [m.group(1) for a in attempts if (m := _NOT_INSTALLED_RE.fullmatch(a))]
    tools = list(dict.fromkeys(missing))
    if attempts and len(missing) == len(attempts):
        return MissingTool(f"{', '.join(tools)} missing: nothing could convert {path.name} ({tried})\n"
                           f"install with: {install_script()}")
    hint = f" (installing {', '.join(tools)} may help: {install_script()})" if tools else ""
    return SkillError(f"could not convert {path.name}: {tried}{hint}")


def convert_pdf(path: Path, attempts: list[str]) -> tuple[Document, str | None]:
    """A PDF with its pages, and the first page's layout (for the title) when pdftotext ran."""
    if (result := pdftotext(path, attempts)) is not None:
        raw, first_page = result
        vocab = vocabulary("\n".join(raw))
        doc = Document("", "pdftotext", [clean_pdf_page(p, vocab) for p in raw])
    elif (text := markitdown(path, attempts)) is not None:
        doc, first_page = Document("", "markitdown", split_pages(text)), None
    else:
        raise no_converter(path, attempts)
    doc.markdown = "\n\n".join(doc.pages)
    return doc, first_page


def convert(path: Path) -> Document:
    ext = path.suffix.lower()
    attempts: list[str] = []
    first_page = None
    if ext in UNSUPPORTED:
        raise SkillError(UNSUPPORTED[ext])
    if ext in MARKDOWN_EXT or ext in PLAIN_EXT:
        doc = Document(read_text(path), "read", language=PLAIN_EXT.get(ext))
    elif ext == ".pdf":
        doc, first_page = convert_pdf(path, attempts)
    else:
        chain = {".rtf": [pandoc, textutil, markitdown], ".doc": [textutil]}.get(ext, [markitdown, pandoc])
        for converter in chain:
            text = converter(path, attempts)
            if usable(converter.__name__, text, attempts):
                doc = Document(pptx_slides(text) if ext == ".pptx" else text, converter.__name__)
                break
        else:
            raise no_converter(path, attempts)
    doc.attempts = attempts
    for a in attempts:
        log(a)
    props = properties(path, doc.markdown, first_page)
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

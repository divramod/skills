"""The text a summary page reads aloud: its note (summary.md / digest.md) as plain sentences. Stdlib only.

Frontmatter, the title header, code blocks, tables, images, HTML comments and URLs are dropped; a link reads as its
label, an anchor link (a timestamp, ¶3, L42, →) not at all: it means nothing to a listener. Reading stops at the links section and
the source's related section (lists of links: "Similar videos", "Further reading", ...).
"""
from __future__ import annotations

import hashlib
import re

# h2 headings that start the lists of links at the end of a note (templates/shared/links.md + each source's related
# section in templates/<source>/template.md): nothing after them is read.
STOP_HEADINGS = ("links", "similar videos", "similar articles", "similar repos", "past discussions",
                 "other posts of this article", "related reading", "also found", "links from the thread",
                 "further reading", "supporting passages")

_FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.S)
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\((?:[^()\s]|\([^()\s]*\))+\)")
_LINK_RE = re.compile(r"\[((?:[^\[\]]|\[[^\]]*\])+)\]\((?:[^()\s]|\([^()\s]*\))+\)")
_URL_RE = re.compile(r"<?\bhttps?://[^\s<>)\]]+>?")
_DATE_LABEL_RE = re.compile(r"\s*\*\([^)]*\d{4}(?:-\d\d){1,2}[^)]*\)\*")


def _inline(text: str) -> str:
    text = _DATE_LABEL_RE.sub("", text)  # check_links.py's "*(published 2025-06-03)*" after a link
    text = _IMAGE_RE.sub("", text)
    # an anchor link ([12:34], [¶3], [L42], [→]) has no word in its label: it means nothing to a listener
    text = _LINK_RE.sub(lambda m: m.group(1) if re.search(r"[^\W\d_]{2}", m.group(1)) else "", text)
    text = _URL_RE.sub("", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"(\*\*|__|\*|(?<!\w)_(?=\S)|(?<=\S)_(?!\w))", "", text)
    while re.search(r"\([\s,;–-]*\)|\[\s*\]", text):  # "(, )" left by the anchors
        text = re.sub(r"\([\s,;–-]*\)|\[\s*\]", "", text)
    return re.sub(r"\s+([,.;:!?])", r"\1", re.sub(r"[ \t]+", " ", text)).strip()


def _sentence(text: str) -> str:
    """A heading or list item read as its own sentence: end it with a full stop so the voice pauses."""
    return text if not text or text[-1] in ".!?:;…" else text + "."


def speech_text(note: str) -> str:
    """Plain text of a note, one paragraph per block and per list item; headings and list items become sentences."""
    body = _FRONTMATTER_RE.sub("", note, count=1)
    lines = body.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    title_done = in_code = in_comment = False
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if in_comment or s.startswith("<!--"):
            in_comment = "-->" not in s
            continue
        if not s or s.startswith("|") or re.fullmatch(r"(-\s*){3,}|(\*\s*){3,}|(_\s*){3,}", s):
            if not s:
                out.append("")
            continue
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*$", s)
        if m:
            level, heading = len(m.group(1)), _inline(m.group(2))
            if level == 1 and not title_done:  # save_summary.py's "# title" + info line: the page shows them
                title_done = True
                out.append(_sentence(heading))
                if i + 2 < len(lines) and not lines[i + 1].strip():
                    lines[i + 2] = ""  # the info line (author · duration · date · url)
                continue
            if level == 2 and heading.rstrip(".").lower() in STOP_HEADINGS:
                break
            out += ["", _sentence(heading), ""]
            continue
        s = re.sub(r"^>\s?", "", s)
        item = re.match(r"^([-*+]|\d+[.)])\s+(\[[ xX]\]\s+)?", s)
        text = _inline(s[item.end():] if item else s)
        if text and item:  # a list item is a paragraph of its own: a pause after it, and a short part to play
            out += ["", _sentence(text), ""]
        elif text:
            out.append(text)
    paragraphs, cur = [], []
    for piece in out + [""]:
        if piece:
            cur.append(piece)
        elif cur:
            paragraphs.append(" ".join(cur))
            cur = []
    return "\n\n".join(paragraphs)


def text_hash(text: str) -> str:
    """Identifies the text an audio file was made from: the page offers a new recording when the note changed."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

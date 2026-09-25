#!/usr/bin/env python3
"""Anchor links for markdown files of a GitHub repo, pinned to a commit so they never drift.

Every paragraph, top-level list item and quote gets `[L<n>](https://github.com/<o>/<r>/blob/<sha>/<path>?plain=1#L<n>)` (the
source view at that line; `?plain=1` because GitHub renders markdown otherwise and ignores #L), and every heading
`[#](…/blob/<sha>/<path>#<slug>)` (GitHub's heading anchor). Relative links point at the same commit: files at
`blob/`, images at raw.githubusercontent.com. Headings are pushed below the file's own section heading.
"""
from __future__ import annotations

import re
import urllib.parse

GITHUB = "https://github.com/"
RAW = "https://raw.githubusercontent.com/"


def slug(heading: str, seen: dict[str, int]) -> str:
    """GitHub's heading anchor: lower case, punctuation dropped (not - or _), spaces -> -, -1/-2 for repeats."""
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", heading)  # links -> their text
    text = re.sub(r"<[^>]+>|[`*]", "", text).strip().lower()
    base = re.sub(r"[^\w\- ]", "", text).replace(" ", "-")
    n = seen.get(base, 0)
    seen[base] = n + 1
    return base if n == 0 else f"{base}-{n}"


IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".avif", ".bmp", ".ico")
# [label](target "title"): the label may hold one level of brackets (a badge: [![alt](img.png)](docs/x.md)),
# the target may be <in angle brackets>, the title is kept as written
LINK = re.compile(r"""(!?)\[((?:[^\[\]]|\[[^\[\]]*\])*)\]\(\s*(<[^>\n]*>|[^)\s]+)((?:\s+(?:"[^"]*"|'[^']*'|\([^)]*\)))?\s*)\)""")
HTML_ATTR = re.compile(r"""(<(img|a|source)\b[^>]*?\b(src|href|srcset)=)(["'])([^"']+)\4""", re.I)
REF_DEF = re.compile(r"^( {0,3}\[[^\]]+\]:\s*)(<[^>]*>|\S+)(.*)$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def is_relative(target: str) -> bool:
    return bool(target) and not re.match(r"^[a-z][a-z0-9+.-]*:|^#|^//", target, re.I)


def pinned(target: str, repo: str, sha: str, folder: str, image: bool) -> str:
    """A relative target -> the file at this commit (images: the raw file, anything else: the blob view)."""
    clean = urllib.parse.urljoin("/" + folder, target).lstrip("/")
    return (f"{RAW}{repo}/{sha}/" if image else f"{GITHUB}{repo}/blob/{sha}/") + clean


def absolutize(markdown: str, repo: str, sha: str, path: str) -> str:
    """Relative link targets -> the file at this commit; relative images -> the raw file. Handles badge links
    (the image inside, the link around it), `[x](path "title")`, <angle> targets, reference definitions
    (`[x]: path`) and HTML `<img src>` / `<a href>`."""
    folder = path.rsplit("/", 1)[0] + "/" if "/" in path else ""

    def fix(m: re.Match) -> str:
        bang, label, target, title = m.group(1), m.group(2), m.group(3), m.group(4)
        label = LINK.sub(fix, label)  # the image of a badge link
        angle = target.startswith("<")
        bare = target[1:-1] if angle else target
        if not is_relative(bare):
            return f"{bang}[{label}]({target}{title})"
        new = pinned(bare, repo, sha, folder, bool(bang))
        return f"{bang}[{label}]({f'<{new}>' if angle else new}{title})"

    def fix_html(m: re.Match) -> str:
        tag, attr, target = m.group(2).lower(), m.group(3).lower(), m.group(5)
        if attr == "srcset" or not is_relative(target):
            return m.group(0)
        return f"{m.group(1)}{m.group(4)}{pinned(target, repo, sha, folder, tag != 'a')}{m.group(4)}"

    def fix_def(m: re.Match) -> str:
        target = m.group(2).strip("<>")
        if not is_relative(target):
            return m.group(0)
        image = target.lower().split("?")[0].split("#")[0].endswith(IMAGE_EXT)
        return f"{m.group(1)}{pinned(target, repo, sha, folder, image)}{m.group(3)}"

    out = LINK.sub(fix, markdown)
    out = HTML_ATTR.sub(fix_html, out)
    return "\n".join(REF_DEF.sub(fix_def, line) for line in out.split("\n"))


def anchor_file(markdown: str, repo: str, sha: str, path: str, demote: int = 2, note: str = "") -> str:
    """The file with [L<n>] line anchors on every text block and [#] on headings (see the module doc). Line
    numbers count "\n" only, as GitHub does. A fence left open (a file cut in a code block) is closed. `note`
    (e.g. the cut note) goes after the file, without an anchor."""
    blob = f"{GITHUB}{repo}/blob/{sha}/{urllib.parse.quote(path)}"
    out: list[str] = []
    seen: dict[str, int] = {}
    fence = ""  # the opening fence (``` or ~~~~, ...) while inside a code block
    start = True  # the next non-blank line starts a block
    for n, line in enumerate(markdown.split("\n"), 1):
        line = line.rstrip("\r")
        stripped = line.strip()
        f = FENCE.match(line)
        if fence:
            # only a fence of the same character, at least as long, with nothing after it closes the block
            if f and f.group(1)[0] == fence[0] and len(f.group(1)) >= len(fence) and not f.group(2).strip():
                fence = ""
            out.append(line)
            continue
        if f and not (f.group(1)[0] == "`" and "`" in f.group(2)):
            fence = f.group(1)
            out.append(line)
            start = False
            continue
        if not stripped:
            out.append(line)
            start = True
            continue
        line = absolutize(line, repo, sha, path)
        heading = re.match(r"(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if heading:
            level = min(6, len(heading.group(1)) + demote)
            out.append(f"{'#' * level} {heading.group(2)} [#]({blob}#{slug(heading.group(2), seen)})")
            start = True
            continue
        item = re.match(r" {0,3}(?:[-*+]|\d+[.)])\s", line)  # every top-level list item gets its own anchor
        if (start or item) and not re.match(r"\s*(<!--|\||[-*_]{3,}\s*$)", line) \
                and not line.startswith(("    ", "\t")):
            m = re.match(r"^(\s*(?:[-*+]|\d+[.)]|>)\s+)", line)
            link = f"[L{n}]({blob}?plain=1#L{n})"
            line = f"{m.group(1)}{link} {line[m.end():]}" if m else f"{link} {line}"
        start = False
        out.append(line)
    if fence:
        out.append(fence)
    text = "\n".join(out).strip()
    return f"{text}\n\n{note}" if note else text

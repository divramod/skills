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


def absolutize(markdown: str, repo: str, sha: str, path: str) -> str:
    """Relative link targets -> the file at this commit; relative images -> the raw file."""
    folder = path.rsplit("/", 1)[0] + "/" if "/" in path else ""

    def fix(m: re.Match) -> str:
        bang, label, target = m.group(1), m.group(2), m.group(3)
        if re.match(r"^[a-z][a-z0-9+.-]*:|^#|^//", target, re.I):
            return m.group(0)
        clean = urllib.parse.urljoin("/" + folder, target).lstrip("/")
        base = f"{RAW}{repo}/{sha}/" if bang else f"{GITHUB}{repo}/blob/{sha}/"
        return f"{bang}[{label}]({base}{clean})"
    return re.sub(r"(!?)\[([^\]]*)\]\(([^)\s]+)\)", fix, markdown)


def anchor_file(markdown: str, repo: str, sha: str, path: str, demote: int = 2) -> str:
    """The file with [L<n>] line anchors on every text block and [#] on headings (see the module doc)."""
    blob = f"{GITHUB}{repo}/blob/{sha}/{urllib.parse.quote(path)}"
    lines = absolutize(markdown, repo, sha, path).splitlines()
    out: list[str] = []
    seen: dict[str, int] = {}
    fence = False
    start = True  # the next non-blank line starts a block
    for n, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            fence = not fence
            out.append(line)
            start = False
            continue
        if fence:
            out.append(line)
            continue
        if not stripped:
            out.append(line)
            start = True
            continue
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
    return "\n".join(out).strip()

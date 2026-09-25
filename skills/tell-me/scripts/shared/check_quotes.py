#!/usr/bin/env python3
"""Check that every quote in a summary body appears verbatim in the item's content file.

Reads the body (stdin, --file, or the folder's summary.md with --summary) and the folder's content file, finds the
quoted passages ("..." or “...”, three words or more; shorter ones are terms, not quotes) and looks each one up.
Whitespace, case, HTML entities, curly vs straight quotes and dashes, markdown emphasis and escapes and the source's own
anchor links ([¶n], [#], [→], [L<n>]) are ignored. An ellipsis (... or … or [...]) may skip text: the parts must appear
in order. Prints one JSON object: {"checked": n, "found": [...], "missing": [...]}. Exit code 1 when a quote is
missing: fix it (copy it from the content file) or paraphrase it without quote marks, then check again.

Usage: check_quotes.py <dir> [--file F | --summary] < body.md
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

from _common import SkillError, contract, log, read_json, run_main

MIN_WORDS = 3
# a straight quote opens after a non-word character (not the inch mark in `12"`) and closes before one
_QUOTE_RE = re.compile(r"“([^”]+)”|(?<!\w)\"([^\"]+)\"(?!\w)")
# a block: a paragraph or one list item / quote line (a quote may wrap over lines inside it)
_BLOCK_RE = re.compile(r"\n\s*\n|\n(?=\s*(?:[-*+>]|\d+[.)])\s)")
_ESCAPE_RE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!<>|~\"'])")
# the end of an attributed quote: `..." (**author**`
_ATTRIBUTION_RE = re.compile(r"[\"”]\s*\(\*\*")
_ELLIPSIS_RE = re.compile(r"\s*(?:\[\s*(?:\.\.\.|…)\s*\]|\.\.\.|…)\s*")
_ANCHOR_RE = re.compile(r"\[(?:¶\d+|#|→|L\d+)\]\([^)\s]*\)")
_LINK_RE = re.compile(r"!?\[([^\[\]]*)\]\([^)\s]*\)")
_CODE_RE = re.compile(r"```.*?```|`[^`\n]*`", re.S)


def norm(text: str) -> str:
    """Text for matching: no anchors, links reduced to their label, entities decoded, one kind of quote, dash and
    apostrophe, no emphasis markers, single spaces, lower case."""
    text = _LINK_RE.sub(r"\1", _ANCHOR_RE.sub("", text))
    text = html.unescape(_ESCAPE_RE.sub(r"\1", text))
    text = text.translate(str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "}))
    text = re.sub(r"(?<!\w)[*_]+|[*_]+(?!\w)", "", text)
    return " ".join(text.split()).lower()


def quotes(body: str) -> list[str]:
    """The quoted passages of a summary body, outside code. An attributed quote is taken whole first."""
    body = _CODE_RE.sub(" ", body)
    found = []
    for block in _BLOCK_RE.split(body):
        line = " ".join(block.split())
        rest = line
        for start, end in attributed(line):
            found.append(line[start + 1:end])
            rest = rest.replace(line[start:end + 1], " ")
        found += [m.group(1) or m.group(2) for m in _QUOTE_RE.finditer(rest)]
    return list(dict.fromkeys(q.strip() for q in found if len(_ELLIPSIS_RE.sub(" ", q).split()) >= MIN_WORDS))


def attributed(line: str) -> list[tuple[int, int]]:
    """(opening, closing) quote positions of each attributed quote. Walking back from the closing mark, quote marks
    pair up by position (an opening one follows a space or line start, a closing one precedes a space or
    punctuation), so a quote inside the quote ("most "founders" know") stays inside it."""
    spans = []
    for m in _ATTRIBUTION_RE.finditer(line):
        end, depth = m.start(), 0
        for i in range(end - 1, -1, -1):
            c = line[i]
            if c not in "\"“”":
                continue
            opening = c == "“" or (c == '"' and (i == 0 or not line[i - 1].isalnum()) and
                                   i + 1 < len(line) and not line[i + 1].isspace())
            if not opening:
                depth += 1
            elif depth:
                depth -= 1
            else:
                spans.append((i, end))
                break
    return spans


def found_in(quote: str, content: str) -> bool:
    """The quote's parts (split at ellipses), each without its outer punctuation, in order in the content."""
    pos = 0
    for part in _ELLIPSIS_RE.split(quote):
        part = norm(part).strip(" .,;:!?\"'()")
        if not part:
            continue
        at = content.find(part, pos)
        if at < 0:
            return False
        pos = at + len(part)
    return True


def check(body: str, content: str) -> dict:
    content = norm(content)
    qs = quotes(body)
    missing = [q for q in qs if not found_in(q, content)]
    return {"checked": len(qs), "found": [q for q in qs if q not in missing], "missing": missing}


def content_of(folder: Path) -> str:
    meta = read_json(folder / "metadata.json")
    path = folder / (contract(meta)["content_file"] or "content.md") if meta else folder / "content.md"
    if not path.exists():
        raise SkillError(f"no content file in {folder} (expected {path.name})")
    return path.read_text(encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir", type=Path, help="the item's library folder (holds the content file)")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--file", type=Path, help="markdown file to check")
    src.add_argument("--summary", action="store_true", help="check the folder's summary.md")
    args = ap.parse_args(argv)
    if args.summary:
        body = (args.dir / "summary.md").read_text(encoding="utf-8")
    elif args.file:
        body = args.file.read_text(encoding="utf-8")
    else:
        body = sys.stdin.read()
    out = check(body, content_of(args.dir))
    print(json.dumps(out, indent=2, ensure_ascii=False))
    log(f"{out['checked']} quotes checked, {len(out['missing'])} not found in the content file"
        + "".join(f"\nNOT FOUND: {q}" for q in out["missing"]))
    return 1 if out["missing"] else 0


if __name__ == "__main__":
    run_main(main)

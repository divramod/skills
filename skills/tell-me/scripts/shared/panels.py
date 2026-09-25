"""Header panels of the summary pages: one row of facts per source, read only from metadata.json.

Each panel is fn(folder, metadata, url) -> html (empty when there is nothing to show). render_html.py puts the
panel under the page header; the video source's panel is its player (render_html.player_html).
"""
from __future__ import annotations

import html
import re
from pathlib import Path

CSS = """
.facts{display:flex;flex-wrap:wrap;gap:4px 16px;margin:.9rem 0 0;padding:0;list-style:none;font-size:.86rem;color:var(--muted)}
.facts li{white-space:nowrap}
.facts b{color:var(--fg);font-weight:600}
.facts a{color:var(--accent)}
.facts .note{white-space:normal;color:var(--fg)}
"""


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def as_int(n) -> int | None:
    """n as a whole number: an int or float, or a string of digits ("1,234"); None for anything else."""
    if isinstance(n, bool):
        return None
    if isinstance(n, (int, float)):
        return int(n)
    if isinstance(n, str) and re.fullmatch(r"\d{1,3}(,\d{3})+|\d+", n.strip()):
        return int(n.strip().replace(",", ""))
    return None


def num(n) -> str | None:
    """12345 -> 12.3k (whole numbers below 10,000); None when n is no number."""
    n = as_int(n)
    if n is None:
        return None
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 10_000:
        return f"{n / 1000:.1f}k".replace(".0k", "k")
    return f"{n:,}"


def plural(n: int, word: str) -> str:
    return f"{word}" if n == 1 else f"{word}s"


def text(value) -> str | None:
    """A string or number to show, else None (a dict, a list or None from unexpected metadata)."""
    return str(value) if isinstance(value, (str, int, float)) and not isinstance(value, bool) and str(value) else None


def extras_of(meta: dict) -> dict:
    ex = meta.get("extras")
    return ex if isinstance(ex, dict) else {}


def facts(*items: str | None) -> str:
    """The panel: one <li> per fact that is set."""
    shown = [i for i in items if i]
    return f'<ul class="facts">{"".join(f"<li>{i}</li>" for i in shown)}</ul>' if shown else ""


def count(n, label: str) -> str | None:
    """`<b>1.2k</b> likes`, or None when n is missing or no number (0 is shown)."""
    shown = num(n)
    return None if shown is None else f"<b>{shown}</b> {label}"


def link(href, text: str) -> str | None:
    """A link that opens in a new tab: only http(s) URLs (a `javascript:` URL from a fetched page is dropped)."""
    if not isinstance(href, str) or not re.match(r"https?://", href, re.I):
        return None
    return f'<a href="{esc(href)}" target="_blank" rel="noopener">{esc(text)}</a>'


def local_link(folder: Path, name, text: str) -> str | None:
    """A link to a file in the summary's folder (a plain file name that exists there)."""
    if not isinstance(name, str) or not re.fullmatch(r"[\w.\- ]+", name) or not (folder / name).is_file():
        return None
    return f'<a href="{esc(name)}" target="_blank" rel="noopener">{esc(text)}</a>'


def web(folder: Path, meta: dict, url: str | None) -> str:
    ex = extras_of(meta)
    words = as_int(meta.get("word_count")) or 0
    return facts(
        esc(meta["site"]) if text(meta.get("site")) else None,
        f"<b>{max(1, round(words / 230))} min</b> read" if words else None,
        f"language {esc(ex['language'])}" if text(ex.get("language")) else None,
        link(ex.get("snapshot"), "archived copy (the live page is gone)" if ex.get("gone") else "archived copy"),
    )


def languages(value) -> str | None:
    """The top 3 languages: a list, a {language: bytes} dict (largest first) or a string."""
    if isinstance(value, dict):
        value = sorted(value, key=lambda k: -(as_int(value[k]) or 0))
    if isinstance(value, list):
        names = [str(v) for v in value[:3] if text(v)]
        return esc(", ".join(names)) if names else None
    return esc(value) if text(value) else None


def github(folder: Path, meta: dict, url: str | None) -> str:
    ex = extras_of(meta)
    if ex.get("kind", "repo") == "repo":
        release = ex.get("release") if isinstance(ex.get("release"), dict) else {}
        license_ = text(ex.get("license"))
        return facts(
            count(ex.get("stars"), "stars"), count(ex.get("forks"), "forks"),
            esc(license_) if license_ and license_ != "NOASSERTION" else None,
            languages(ex.get("languages")),
            f"release <b>{esc(release['tag'])}</b>" + (f" ({esc(release['date'])})" if text(release.get("date")) else "")
            if text(release.get("tag")) else None,
            f"last push {esc(ex['pushed_at'])}" if text(ex.get("pushed_at")) else None,
            "<b>archived</b>" if ex.get("archived") is True else None,
            f"fork of {esc(ex['fork_of'])}" if text(ex.get("fork_of")) else None,
        )
    state = "merged" if ex.get("merged") is True else text(ex.get("state"))
    if state == "closed" and text(ex.get("state_reason")):
        state += f" ({str(ex['state_reason']).replace('_', ' ')})"
    labels = [str(label) for label in ex["labels"] if text(label)] if isinstance(ex.get("labels"), list) else []
    added, removed, files = (as_int(ex.get(k)) for k in ("additions", "deletions", "changed_files"))
    repo = text(ex.get("repo"))
    return facts(
        f"{esc(ex['kind'])} <b>#{esc(text(ex.get('number')) or '')}</b>" if text(ex.get("kind")) else None,
        f"<b>{esc(state)}</b>" if state else None,
        count(ex.get("comments"), "comments"),
        f"<b>+{added or 0:,} −{removed or 0:,}</b> in {files or 0:,} {plural(files or 0, 'file')}"
        if added is not None or removed is not None else None,
        esc(", ".join(labels)) if labels else None,
        link(f"https://github.com/{repo}", repo) if repo and re.fullmatch(r"[\w.-]+/[\w.-]+", repo) else None,
    )


def x(folder: Path, meta: dict, url: str | None) -> str:
    ex = extras_of(meta)
    replies, fetched, posts = as_int(ex.get("replies")), as_int(ex.get("replies_fetched")), as_int(ex.get("posts"))
    read = f" ({num(fetched)} read)" if fetched is not None and replies is not None and fetched != replies else ""
    user = text(ex.get("user"))
    return facts(
        link(f"https://x.com/{user}", f"@{user}") if user and re.fullmatch(r"\w{1,50}", user) else None,
        count(ex.get("views"), "views"), count(ex.get("likes"), "likes"), count(ex.get("reposts"), "reposts"),
        f"<b>{num(replies)}</b> replies{read}" if replies is not None else None,
        f"<b>{posts:,}</b> posts in the thread" if (posts or 0) > 1 else None,
        '<span class="note">⚑ <b>community note</b></span>' if ex.get("community_note") else None,
    )


def hn(folder: Path, meta: dict, url: str | None) -> str:
    ex = extras_of(meta)
    comments, threads = as_int(ex.get("comments")), as_int(ex.get("threads"))
    in_threads = f" in {threads:,} {plural(threads, 'thread')}" if threads else ""
    article = link(ex.get("article_url"), "the article")
    known = as_int(ex.get("points")) is not None or comments is not None  # a story we read, not a bare comment
    return facts(
        count(ex.get("points"), "points"),
        f"<b>{num(comments)}</b> comments{in_threads}" if comments is not None else None,
        article or ("text post" if known and not ex.get("article_url") else None),
        link(ex.get("snapshot"), "archived copy"),
    )


def reddit(folder: Path, meta: dict, url: str | None) -> str:
    ex = extras_of(meta)
    comments, threads, ratio = as_int(ex.get("comments")), as_int(ex.get("threads")), ex.get("upvote_ratio")
    in_threads = f" in {threads:,} {plural(threads, 'thread')}" if threads else ""
    sub = text(ex.get("subreddit"))
    upvoted = f" ({round(ratio * 100)}% upvoted)" if isinstance(ratio, float) and 0 < ratio <= 1 else ""
    points = count(ex.get("score"), "points")
    return facts(
        link(f"https://www.reddit.com/r/{sub}/", f"r/{sub}") if sub and re.fullmatch(r"\w{1,50}", sub) else None,
        points + upvoted if points else None,
        f"<b>{num(comments)}</b> comments{in_threads}" if comments is not None else None,
        f"flair: {esc(ex['flair'])}" if text(ex.get("flair")) else None,
        link(ex.get("article_url"), "the article") or link(ex.get("media"), "the media"),
        link(ex.get("snapshot"), "archived copy"),
        "from the Arctic Shift archive" if ex.get("api") == "arctic" else None,
    )


def file(folder: Path, meta: dict, url: str | None) -> str:
    ex = extras_of(meta)
    size = as_int(ex.get("size"))
    versions = ex.get("versions") if isinstance(ex.get("versions"), list) else []
    return facts(
        f"<b>{esc(ex['kind'].upper())}</b>" if isinstance(ex.get("kind"), str) and ex["kind"] else None,
        count(ex.get("pages"), "pages"),
        f"{size / 2**20:.1f} MB" if size and size >= 2**20 else f"{max(1, round(size / 1024))} KB" if size else None,
        local_link(folder, ex.get("original_file"), "open the original"),
        f"version {len(versions) + 1}" if versions else None,
    )


PANELS = {"web": web, "github": github, "x": x, "hn": hn, "reddit": reddit, "file": file}

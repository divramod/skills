"""Header panels of the summary pages: one row of facts per source, read only from metadata.json.

Each panel is fn(folder, metadata, url) -> html (empty when there is nothing to show). render_html.py puts the
panel under the page header; the video source's panel is its player (render_html.player_html).
"""
from __future__ import annotations

import html
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


def num(n) -> str:
    """12345 -> 12.3k (whole numbers below 10,000)."""
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 10_000:
        return f"{n / 1000:.1f}k".replace(".0k", "k")
    return f"{n:,}"


def facts(*items: str | None) -> str:
    """The panel: one <li> per fact that is set."""
    shown = [i for i in items if i]
    return f'<ul class="facts">{"".join(f"<li>{i}</li>" for i in shown)}</ul>' if shown else ""


def count(n, label: str) -> str | None:
    """`<b>1.2k</b> likes`, or None when n is missing (0 is shown)."""
    return None if n is None else f"<b>{num(n)}</b> {label}"


def link(href: str | None, text: str) -> str | None:
    return f'<a href="{esc(href)}" target="_blank" rel="noopener">{esc(text)}</a>' if href else None


def web(folder: Path, meta: dict, url: str | None) -> str:
    ex = meta.get("extras") or {}
    words = meta.get("word_count") or 0
    return facts(
        esc(meta.get("site")) if meta.get("site") else None,
        f"<b>{max(1, round(words / 230))} min</b> read" if words else None,
        f"language {esc(ex['language'])}" if ex.get("language") else None,
        link(ex.get("snapshot"), "archived copy (the live page is gone)" if ex.get("gone") else "archived copy"),
    )


def github(folder: Path, meta: dict, url: str | None) -> str:
    ex = meta.get("extras") or {}
    if ex.get("kind", "repo") == "repo":
        langs = ex.get("languages") or []
        release = ex.get("release") or {}
        return facts(
            count(ex.get("stars"), "stars"), count(ex.get("forks"), "forks"),
            esc(ex["license"]) if ex.get("license") and ex["license"] != "NOASSERTION" else None,
            esc(", ".join(str(lang) for lang in langs[:3])) if isinstance(langs, list) and langs else
            (esc(langs) if isinstance(langs, str) else None),
            f"release <b>{esc(release['tag'])}</b>" + (f" ({esc(release['date'])})" if release.get("date") else "")
            if release.get("tag") else None,
            f"last push {esc(ex['pushed_at'])}" if ex.get("pushed_at") else None,
            "<b>archived</b>" if ex.get("archived") else None,
            f"fork of {esc(ex['fork_of'])}" if ex.get("fork_of") else None,
        )
    state = "merged" if ex.get("merged") else ex.get("state")
    if state == "closed" and ex.get("state_reason"):
        state += f" ({ex['state_reason'].replace('_', ' ')})"
    return facts(
        f"{esc(ex['kind'])} <b>#{esc(ex.get('number', ''))}</b>" if ex.get("kind") else None,
        f"<b>{esc(state)}</b>" if state else None,
        count(ex.get("comments"), "comments"),
        f"<b>+{ex.get('additions', 0):,} −{ex.get('deletions', 0):,}</b> in {ex.get('changed_files', 0)} files"
        if "additions" in ex else None,
        esc(", ".join(ex["labels"])) if ex.get("labels") else None,
        link(f"https://github.com/{ex['repo']}", ex["repo"]) if ex.get("repo") else None,
    )


def x(folder: Path, meta: dict, url: str | None) -> str:
    ex = meta.get("extras") or {}
    replies, fetched = ex.get("replies"), ex.get("replies_fetched")
    read = f" ({num(fetched)} read)" if fetched is not None and replies is not None and fetched != replies else ""
    return facts(
        link(f"https://x.com/{ex['user']}", f"@{ex['user']}") if ex.get("user") else None,
        count(ex.get("views"), "views"), count(ex.get("likes"), "likes"), count(ex.get("reposts"), "reposts"),
        f"<b>{num(replies)}</b> replies{read}" if replies is not None else None,
        f"<b>{ex['posts']}</b> posts in the thread" if (ex.get("posts") or 0) > 1 else None,
        '<span class="note">⚑ <b>community note</b></span>' if ex.get("community_note") else None,
    )


def hn(folder: Path, meta: dict, url: str | None) -> str:
    ex = meta.get("extras") or {}
    threads = f" in {ex['threads']} threads" if ex.get("threads") else ""
    return facts(
        count(ex.get("points"), "points"),
        f"<b>{num(ex['comments'])}</b> comments{threads}" if ex.get("comments") is not None else None,
        link(ex.get("article_url"), "the article") if ex.get("article_url") else "text post",
        link(ex.get("snapshot"), "archived copy"),
    )


def file(folder: Path, meta: dict, url: str | None) -> str:
    ex = meta.get("extras") or {}
    original = ex.get("original_file")
    size = ex.get("size")
    versions = ex.get("versions") or []
    return facts(
        f"<b>{esc(ex['kind'].upper())}</b>" if ex.get("kind") else None,
        count(ex.get("pages"), "pages"),
        f"{size / 2**20:.1f} MB" if size and size >= 2**20 else f"{max(1, round(size / 1024))} KB" if size else None,
        link(original, "open the original") if original and (folder / original).exists() else None,
        f"version {len(versions) + 1}" if versions else None,
    )


PANELS = {"web": web, "github": github, "x": x, "hn": hn, "file": file}

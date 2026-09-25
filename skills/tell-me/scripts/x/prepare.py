#!/usr/bin/env python3
"""Prepare an X (Twitter) post for summarizing: the thread, the replies and the transcript of its video.

1. The post id (route.py) is the id; a post of a thread prepares the whole thread, whose first post is the id
   (the linked post is stored as an alias and named in the envelope's `focus_post`). A prepared thread is reused
   (--refresh refetches, e.g. when the replies have grown).
2. client.py: the thread (the author's chain) and up to --max-replies replies from FxTwitter; X's embed endpoint
   as the fallback for the post alone. A reply to someone else's post gets that post as context.
3. The first video in the thread goes through the video source (`video/prepare.py <post url> --dir <folder>
   --content-part video`): its transcript becomes `## Video` and it downloads in the background (best quality;
   --skip-download keeps no video, --no-video skips the video part). Without yt-dlp the video part is skipped
   and noted.
4. content.md: a header, `## Thread` (one `### n/N` per post with its permalink, quoted posts, media, polls, link
   cards, community notes), `## Video`, then `## Replies` with one line per reply:
   `- **@user** [→](<permalink>) (n likes, reply to @user): text`, replies to a reply right below it.
5. metadata.json: the shared contract fields (extras: user, name, views, likes, reposts, replies, quotes,
   bookmarks, replies_fetched, posts, community_note, api, attempts, aliases).
Folder: <root>/posts/x/<user>/<first-words>-<id>/. Prints the source envelope on stdout.

Usage: prepare.py <post url|id> [--refresh] [--max-replies N] [--skip-download] [--no-video]
Requires: nothing (urllib); yt-dlp + ffmpeg for a post with a video.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.append(str(SCRIPTS / "shared"))  # _common + the shared steps
sys.path.insert(0, str(Path(__file__).resolve().parent))  # client.py (before video/, which has a prepare.py too)

from _common import SkillError, envelope, find_by_id, fmt_ts, log, read_json, run_main, unique_dir, update_json
from client import FxTwitter
from route import route

VIDEO_PREPARE = SCRIPTS / "video" / "prepare.py"
MAX_REPLIES = 200
TITLE_CHARS = 80
_URL_RE = re.compile(r"https?://\S+")
_LEAD_MENTIONS_RE = re.compile(r"^(?:@\w+\s+)+")


# ---------------------------------------------------------------- text


def handle(status: dict) -> str:
    return (status.get("author") or {}).get("screen_name") or "unknown"


def iso(status: dict) -> str | None:
    """The post's date (YYYY-MM-DD)."""
    ts = status.get("created_timestamp")
    if ts:
        return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")
    raw = status.get("created_at") or ""
    for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def title_of(status: dict) -> str:
    """The post's first words (no links), cut at a word near TITLE_CHARS; else "Post by @user"."""
    article = status.get("article") or {}
    if article.get("title"):
        return article["title"]
    text = " ".join(_URL_RE.sub("", _LEAD_MENTIONS_RE.sub("", status.get("text") or "")).split())
    if not text:
        return f"Post by @{handle(status)}"
    if len(text) <= TITLE_CHARS:
        return text
    cut = text[:TITLE_CHARS].rsplit(" ", 1)[0]
    return cut.rstrip(",;:-") + "…"


def reply_text(status: dict) -> str:
    """The text without the leading @mentions X adds to every reply."""
    text = status.get("text") or ""
    return _LEAD_MENTIONS_RE.sub("", text).strip() if status.get("replying_to") else text.strip()


def indent(text: str, prefix: str = "  ") -> str:
    """Later lines of a multi-line text, indented to stay inside their list item or quote."""
    return "\n".join(line if i == 0 or not line else prefix + line for i, line in enumerate(text.splitlines()))


def counts(status: dict, keys=("likes", "reposts", "replies", "views")) -> str:
    return ", ".join(f"{status[k]:,} {k}" for k in keys if status.get(k))


def media_lines(status: dict) -> list[str]:
    media = status.get("media") or {}
    lines = []
    for i, p in enumerate(media.get("photos") or [], 1):
        alt = f": {p['altText']}" if p.get("altText") else ""
        lines.append(f"- [{'GIF' if p.get('type') == 'gif' else 'photo'} {i}]({p.get('url')}){alt}")
    for i, v in enumerate(media.get("videos") or [], 1):
        what = "GIF" if v.get("type") == "gif" else f"video {i} ({fmt_ts(v.get('duration') or 0)})"
        lines.append(f"- [{what}]({v.get('url')})")
    if (ext := media.get("external")) and ext.get("url"):
        lines.append(f"- [embedded video]({ext['url']})")
    return lines


def extras_lines(status: dict) -> list[str]:
    """Poll, link card, X article, community note: one block each."""
    out = []
    poll = status.get("poll") or {}
    if poll.get("choices"):
        out.append(f"Poll ({poll.get('total_votes', 0):,} votes):")
        out += [f"- {c.get('label')}: {c.get('percentage')}%" for c in poll["choices"]]
    card = status.get("card") or {}
    if card.get("url") and card.get("title"):
        desc = f": {card['description']}" if card.get("description") else ""
        out.append(f"Link card: [{card['title']}]({card['url']}){desc}")
    article = status.get("article") or {}
    if article.get("title"):
        out.append(f"X article: **{article['title']}**: {article.get('preview_text') or ''}".rstrip(": "))
    note = status.get("community_note") or {}
    if note.get("text"):
        out.append(f"**Community note:** {indent(note['text'].strip())}")
    return out


def quote_block(quote: dict | None) -> list[str]:
    if not isinstance(quote, dict):
        return []
    if quote.get("type") == "tombstone":
        return [f"> Quoted post unavailable: {quote.get('message') or quote.get('reason') or 'unavailable'}"]
    head = f"> Quoting **@{handle(quote)}** [→]({quote.get('url')}) ({iso(quote) or '?'}):"
    body = [f"> {line}" if line else ">" for line in (quote.get("text") or "").strip().splitlines()]
    body += [f"> {line}" for line in media_lines(quote)]
    return [head] + body


def post_block(status: dict, n: int, total: int, focus: str | None) -> str:
    here = " (the linked post)" if focus and status.get("id") == focus and total > 1 else ""
    head = f"### {n}/{total} [→]({status.get('url')}) · {iso(status) or '?'}"
    stats = counts(status)
    parts = [head + (f" · {stats}" if stats else "") + here, "", reply_text(status) if n > 1 else
             (status.get("text") or "").strip()]
    for block in (quote_block(status.get("quote")), media_lines(status), extras_lines(status)):
        if block:
            parts += ["", "\n".join(block)]
    return "\n".join(parts)


def replies_md(replies: list[dict], thread: list[dict]) -> tuple[str, int]:
    """(the ## Replies list, reply count). Top-level replies (to a thread post) by likes; a reply's replies
    right below it, oldest first. A reply to a later thread post says which (`on post n/N`)."""
    position = {str(s["id"]): i for i, s in enumerate(thread, 1)}
    by_id = {r["id"]: r for r in replies if r.get("id") and str(r["id"]) not in position}
    children: dict[str, list[dict]] = {}
    top = []
    for r in by_id.values():
        parent = (r.get("replying_to") or {}).get("status")
        if parent in by_id:
            children.setdefault(parent, []).append(r)
        else:
            top.append(r)
    lines: list[str] = []

    def walk(r: dict, parent: str | None) -> None:
        likes = r.get("likes") or 0
        facts = [f"{likes:,} like{'s' if likes != 1 else ''}"]
        on = position.get(str((r.get("replying_to") or {}).get("status")))
        if parent:
            facts.append(f"reply to @{parent}")
        elif on and on > 1:
            facts.append(f"on post {on}/{len(thread)}")
        text = reply_text(r)
        quote = r.get("quote")
        if isinstance(quote, dict) and quote.get("type") != "tombstone":
            text += f" [quoting @{handle(quote)}: {' '.join((quote.get('text') or '').split())}]"
        media = [m.split("](")[0].lstrip("- [") for m in media_lines(r)]
        if media:
            text += f" [{', '.join(media)}]"
        lines.append(f"- **@{handle(r)}** [→]({r.get('url')}) ({', '.join(facts)}): {indent(text) or '(no text)'}")
        for child in sorted(children.get(r["id"], []), key=lambda c: c.get("created_timestamp") or 0):
            walk(child, handle(r))

    for r in sorted(top, key=lambda c: -(c.get("likes") or 0)):
        walk(r, None)
    return "\n".join(lines), len(lines)


def render_content(meta: dict, extras: dict, context: dict | None, thread: list[dict], video_md: str,
                   replies: str, focus: str | None) -> str:
    rows = [f"# {meta['title']}", "", f"- url: {meta['url']}", f"- posted by: {meta['author']}"]
    for label, value in (("published", meta.get("published")),
                         ("stats", counts(extras | {"replies": extras.get("replies")},
                                          ("views", "likes", "reposts", "quotes", "bookmarks", "replies"))),
                         ("posts in the thread", len(thread) if len(thread) > 1 else None),
                         ("replies fetched", extras.get("replies_fetched")),
                         ("api", extras.get("api"))):
        if value:
            rows.append(f"- {label}: {value}")
    if context:
        rows += ["", "## In reply to", "", post_block(context, 1, 1, None).replace("### 1/1", "###", 1)]
    rows += ["", "## Thread", ""]
    rows += ["\n\n".join(post_block(s, i, len(thread), focus) for i, s in enumerate(thread, 1)), ""]
    if video_md:
        rows += ["## Video", "", video_md, ""]
    rows += ["## Replies", "", replies or "*No replies fetched.*", ""]
    return "\n".join(rows)


# ---------------------------------------------------------------- video part


def first_video(thread: list[dict]) -> dict | None:
    """The first thread post with a (non-GIF) video."""
    for s in thread:
        if any(v.get("type") != "gif" for v in (s.get("media") or {}).get("videos") or []):
            return s
    return None


def video_part(post: dict, folder: Path, skip_download: bool, refresh: bool, attempts: list[str]) -> str:
    """The `## Video` section: video/prepare.py as a content part of this folder. A failure is noted."""
    cmd = [sys.executable, str(VIDEO_PREPARE), post["url"], "--dir", str(folder), "--content-part", "video"]
    cmd += (["--skip-download"] if skip_download else []) + (["--refresh"] if refresh else [])
    log(f"video: {post['url']} -> the video source (transcript{'' if skip_download else ', background download'})")
    p = subprocess.run(cmd, stdout=subprocess.PIPE, text=True)  # its progress goes to our stderr
    if p.returncode == 2:
        attempts.append("video: skipped, the video tools are missing (run scripts/video/install-prerequisites.sh)")
        log(attempts[-1])
        return f"*The post has a video, but its transcript was skipped: {attempts[-1].split(', ', 1)[1]}.*"
    if p.returncode != 0:
        attempts.append(f"video: the video source failed (exit {p.returncode})")
        log(attempts[-1])
        return "*The post has a video, but its transcript could not be made (see the log above).*"
    part = json.loads(p.stdout)
    text = Path(part["transcript"]).read_text(encoding="utf-8")
    body = text.split("\n## Transcript\n", 1)[-1].strip()
    head = (f"The video of [post {post['id']}]({post['url']}) ({part.get('duration')}, transcript: "
            f"{part.get('transcript_source')}; the full transcript is in `{Path(part['transcript']).name}`).")
    return f"{head}\n\n{body}"


# ---------------------------------------------------------------- main


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("post", help="an x.com/twitter.com post URL or the bare id")
    ap.add_argument("--refresh", action="store_true", help="refetch the thread even if it was prepared before")
    ap.add_argument("--max-replies", type=int, default=MAX_REPLIES, help=f"default {MAX_REPLIES}; 0: none")
    ap.add_argument("--skip-download", action="store_true", help="a post's video: transcript only, no download")
    ap.add_argument("--no-video", action="store_true", help="no video part at all")
    args = ap.parse_args(argv)
    return prepare(args, FxTwitter())


def prepare(args, fx: FxTwitter) -> int:
    r = route(f"https://x.com/i/status/{args.post}" if args.post.isdigit() else args.post)
    if r["source"] != "x":
        raise SkillError(f"{args.post} is a {r['source']} input, not an x.com post")
    existing = find_by_id("x", r["id"])
    if existing and (existing / "content.md").exists() and not args.refresh:
        log(f"reusing: {existing} (pass --refresh to refetch)")
        meta = read_json(existing / "metadata.json")
        return print_envelope(existing, meta, reused=True, focus=r["id"] if r["id"] != meta.get("id") else None)

    thread = fx.thread(r["id"])
    root = thread[0]
    post_id = str(root["id"])
    focus = r["id"] if r["id"] != post_id else None
    if focus and (known := find_by_id("x", post_id)) and (known / "content.md").exists() and not args.refresh:
        log(f"reusing: {known}, the thread of post {focus} (pass --refresh to refetch)")
        return print_envelope(known, read_json(known / "metadata.json"), reused=True, focus=focus)
    existing = existing or find_by_id("x", post_id)
    log(f"{fx.api}: {len(thread)} post{'s' if len(thread) != 1 else ''} in the thread")

    context = None
    parent = (root.get("replying_to") or {}).get("status")
    if parent and fx.api != "syndication":  # a reply to someone else's post: that post as context
        try:
            context = fx.post(parent)[0]
        except SkillError as e:
            fx.note(f"context: the post it replies to could not be fetched ({e})")
    replies = fx.replies(post_id, args.max_replies, root.get("replies")) if args.max_replies > 0 else []
    replies_text, fetched = replies_md(replies, thread)
    log(f"{fetched} replies fetched (the post has {root.get('replies') or 0})")

    old = read_json(existing / "metadata.json") if existing else {}
    aliases = sorted({*((old.get("extras") or {}).get("aliases") or []), *([r["id"]] if focus else [])})
    author = root.get("author") or {}
    extras = {k: v for k, v in {
        "user": handle(root), "name": author.get("name"), "views": root.get("views"), "likes": root.get("likes"),
        "reposts": root.get("reposts"), "replies": root.get("replies"), "quotes": root.get("quotes"),
        "bookmarks": root.get("bookmarks"), "replies_fetched": fetched, "posts": len(thread),
        "community_note": any((s.get("community_note") or {}).get("text") for s in thread) or None,
        "api": fx.api, "attempts": fx.attempts or None, "aliases": aliases or None,
    }.items() if v is not None}
    meta = {
        "source": "x", "id": post_id, "url": root.get("url") or f"https://x.com/{handle(root)}/status/{post_id}",
        "title": title_of(root), "author": f"{author.get('name') or handle(root)} (@{handle(root)})",
        "published": iso(root), "fetched": datetime.now().isoformat(timespec="seconds"), "site": "X",
        "word_count": 0, "duration": None, "extractor": fx.api, "content_file": "content.md", "extras": extras,
    }
    folder = existing or unique_dir(meta)
    folder.mkdir(parents=True, exist_ok=True)
    log(f"{'refreshing' if existing else 'folder'}: {folder}")
    # The contract fields first: the video part's background download tags the file from metadata.json.
    update_json(folder / "metadata.json", meta | {"prepared_at": old.get("prepared_at") or meta["fetched"]})

    video_md = ""
    if (post := first_video(thread)) and not args.no_video:
        video_md = video_part(post, folder, args.skip_download, args.refresh, fx.attempts)
        extras["attempts"] = fx.attempts or None
    content = render_content(meta, extras, context, thread, video_md, replies_text, focus)
    (folder / "content.md").write_text(content, encoding="utf-8")
    meta = update_json(folder / "metadata.json", {"word_count": len(content.split()),
                                                  "extras": {k: v for k, v in extras.items() if v is not None}})
    return print_envelope(folder, meta, reused=bool(existing), focus=focus)


def print_envelope(folder: Path, meta: dict, reused: bool, focus: str | None = None) -> int:
    """The envelope; `focus_post` is this run's linked post when it is not the thread's first."""
    extras = meta.get("extras") or {}
    video = meta.get("video") or {}
    print(json.dumps(envelope(folder, meta, "post", reused=reused, user=extras.get("user"),
                              posts=extras.get("posts"), replies=extras.get("replies"),
                              replies_fetched=extras.get("replies_fetched"), focus_post=focus,
                              community_note=extras.get("community_note"),
                              video_transcript=str(folder / video["transcript_file"]) if video else None,
                              video_file=meta.get("video_file"),
                              video_download=read_json(folder / ".video-download.json") or None,
                              api=extras.get("api"), attempts=extras.get("attempts")),
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    run_main(main)

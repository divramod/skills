#!/usr/bin/env python3
"""Prepare a Reddit post (its text, the linked article and the discussion) for summarizing.

1. The post id (route.py) is the id: an already-prepared post is reused (--refresh refetches, e.g. when the
   discussion has grown). A share link (/r/<sub>/s/<code>) is resolved to its post first. A comment link prepares
   its whole post; the envelope's `focus_comment` names the comment.
2. The post and its comment tree come from the first API that answers (Reddit blocks anonymous requests from many
   networks):
     reddit   www.reddit.com/comments/<id>/.json (anonymous, top-sorted, up to 500 comments)
     oauth    oauth.reddit.com with an app-only token, when REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET are set
     arctic   the Arctic Shift archive (arctic-shift.photon-reddit.com): the full tree; scores settle ~36 h after
              posting, so a young post's scores are stale
   Every failed API is noted in `attempts`. Comments Reddit folds behind "load more" are counted (`not_loaded`),
   not fetched. Deleted and removed comments are dropped, their replies kept. Comments are ordered by score.
3. A link post's page goes through the web source's extractor (trafilatura + defuddle → Jina → Wayback) with its
   [¶n] paragraph anchors, like a Hacker News article; images, galleries and videos hosted on Reddit are only
   named (a v.redd.it video is summarized by the video source). --no-article skips the page.
4. content.md: a header, `## Post` (the post's own text), `## Article` (a link post's page), then `## Discussion`
   with one `### Thread n` per top-level comment and one line per comment:
   `- **author** (OP) [→](<permalink>) (depth n, reply to <author>, <score> points): text`.
5. metadata.json: the shared contract fields (extras: subreddit, score, upvote_ratio, comments, num_comments,
   threads, not_loaded, flair, article_url, media, crosspost_from, over_18, api, attempts, and the article's
   facts). Folder: <root>/discussions/reddit/<subreddit>/<title>-<id>/. Prints the source envelope on stdout.

Usage: prepare.py <post url|id> [--refresh] [--no-article]
Requires: uvx (trafilatura) and npx (defuddle) for a linked article.
"""
from __future__ import annotations

import argparse
import base64
import html
import http.client
import importlib.util
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.append(str(SCRIPTS / "shared"))  # _common + the shared steps
sys.path.append(str(SCRIPTS / "web"))  # the web extractor (a source may use another source; shared may not)

from _common import SkillError, envelope, find_by_id, log, read_json, run_main, unique_dir, update_json
from route import route

REDDIT = "https://www.reddit.com"
OAUTH = "https://oauth.reddit.com"
TOKEN = "https://www.reddit.com/api/v1/access_token"
ARCTIC = "https://arctic-shift.photon-reddit.com/api"
USER_AGENT = "tell-me/1.0 (summarizer; +https://github.com/divramod/skills)"
TIMEOUT = 30
RETRY_WAIT = 3  # seconds before asking the archive again
# Hosts of media Reddit serves itself: named in the header, never extracted as an article.
MEDIA_HOSTS = ("i.redd.it", "v.redd.it", "preview.redd.it", "i.imgur.com", "imgur.com", "gfycat.com",
               "redgifs.com")


@lru_cache(maxsize=1)
def hn_prepare():
    """hn/prepare.py as a module (article(), item_text()): its file name clashes with this one's."""
    spec = importlib.util.spec_from_file_location("hn_prepare", SCRIPTS / "hn" / "prepare.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------- fetch


def get_json(url: str, headers: dict | None = None, data: bytes | None = None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT} | (headers or {}))
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SkillError(f"{url.split('?')[0]} answered HTTP {e.code}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise SkillError(f"could not fetch {url.split('?')[0]}: {getattr(e, 'reason', e)}")
    except (http.client.HTTPException, ValueError):  # a block page, a cut-off answer, bad UTF-8 or JSON
        raise SkillError(f"{url.split('?')[0]} did not answer JSON")


def arctic(path: str):
    """An Arctic Shift answer; asked twice, since it refuses requests for a moment under load (HTTP 422/429)."""
    try:
        return get_json(f"{ARCTIC}/{path}")
    except SkillError as e:
        if not re.search(r"HTTP (422|429|5\d\d)", str(e)):
            raise
        log(f"{e}: asking again in {RETRY_WAIT}s")
        time.sleep(RETRY_WAIT)
        return get_json(f"{ARCTIC}/{path}")


def resolve_share(url: str) -> str:
    """The post URL a share link redirects to. Reddit may refuse the final page (403): its URL is enough."""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            final = r.geturl()
    except urllib.error.HTTPError as e:
        final = e.geturl() or url
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise SkillError(f"could not resolve the share link {url}: {getattr(e, 'reason', e)}")
    if "/comments/" not in final:
        raise SkillError(f"Reddit did not reveal the post behind {url} (got {final}): open it in a browser and pass "
                         "the address it shows (…/comments/<id>/…)")
    return final


def listing(things) -> list[dict]:
    """The children of a Listing (Reddit's `replies` is "" when there are none)."""
    if not isinstance(things, dict):
        return []
    return (things.get("data") or {}).get("children") or []


def from_reddit(answer) -> tuple[dict, list[dict]]:
    """(the post, its top-level comment things) from /comments/<id>.json: [post Listing, comments Listing]."""
    if not isinstance(answer, list) or len(answer) < 2 or not listing(answer[0]):
        raise SkillError("the answer is not a Reddit thread")
    return listing(answer[0])[0]["data"], listing(answer[1])


def oauth_token() -> str | None:
    """An app-only token (client credentials) when REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET are set."""
    cid, secret = os.environ.get("REDDIT_CLIENT_ID"), os.environ.get("REDDIT_CLIENT_SECRET")
    if not cid or not secret:
        return None
    auth = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    answer = get_json(TOKEN, {"Authorization": f"Basic {auth}"}, b"grant_type=client_credentials")
    if not isinstance(answer, dict) or not answer.get("access_token"):
        raise SkillError(f"Reddit gave no token: {answer.get('error') if isinstance(answer, dict) else answer}")
    return answer["access_token"]


def unescape(thing: dict) -> dict:
    """Archived text keeps Reddit's HTML escapes (&amp; &lt; &gt;): undo them, down the whole tree."""
    data = thing.get("data") or {}
    for key in ("body", "selftext", "title"):
        if isinstance(data.get(key), str):
            data[key] = html.unescape(data[key])
    for child in listing(data.get("replies")):
        unescape(child)
    return thing


def fetch_thread(post_id: str, attempts: list[str]) -> tuple[dict, list[dict], str]:
    """(the post, its top-level comment things, the API they came from): Reddit, Reddit OAuth, Arctic Shift."""
    query = "?limit=500&sort=top&raw_json=1"
    try:
        post, comments = from_reddit(get_json(f"{REDDIT}/comments/{post_id}/.json{query}"))
        return post, comments, "reddit"
    except SkillError as e:
        attempts.append(f"reddit: {e}")
    try:
        token = oauth_token()
        if token:
            post, comments = from_reddit(get_json(f"{OAUTH}/comments/{post_id}{query}",
                                                  {"Authorization": f"Bearer {token}"}))
            return post, comments, "oauth"
        attempts.append("oauth: skipped (REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not set)")
    except SkillError as e:
        attempts.append(f"oauth: {e}")
    log(f"{'; '.join(attempts)} -> the Arctic Shift archive")
    try:
        posts = (arctic(f"posts/ids?ids={post_id}") or {}).get("data") or []
        if not posts:
            raise SkillError(f"Reddit has no post {post_id} (or the archive does not have it yet)")
        tree = (arctic(f"comments/tree?link_id={post_id}&limit=25000") or {}).get("data") or []
    except SkillError as e:
        attempts.append(f"arctic: {e}")
        raise SkillError(f"no API answered for Reddit post {post_id}: {'; '.join(attempts)}. Set "
                         "REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET (a free 'script' app at "
                         "https://www.reddit.com/prefs/apps) or try again later")
    post = unescape({"data": posts[0]})["data"]
    return post, [unescape(t) for t in tree], "arctic"


# ---------------------------------------------------------------- text


GONE = {"[deleted]", "[removed]", ""}


def permalink(sub: str, post_id: str, comment_id: str) -> str:
    return f"{REDDIT}/r/{sub}/comments/{post_id}/_/{comment_id}/"


def by_score(things: list[dict]) -> list[dict]:
    """Comments best first (Reddit's "top"); "more" stubs last."""
    return sorted(things, key=lambda t: (t.get("kind") != "t1", -((t.get("data") or {}).get("score") or 0),
                                         (t.get("data") or {}).get("created_utc") or 0))


def discussion(comments: list[dict], sub: str, post_id: str, item_text) -> tuple[str, int, int, int]:
    """(the ## Discussion markdown, comment count, top-level thread count, comments behind "load more")."""
    sections, total, threads, more = [], 0, 0, 0

    def walk(thing: dict, depth: int, parent: str | None, lines: list[str]) -> int:
        nonlocal more
        data = thing.get("data") or {}
        if thing.get("kind") == "more":
            more += data.get("count") or len(data.get("children") or [])
            return 0
        count = 0
        author, body = data.get("author"), (data.get("body") or "").strip()
        alive = author not in GONE and body not in GONE
        if alive:  # a deleted or removed comment: dropped, its replies kept
            op = " (OP)" if data.get("is_submitter") else ""
            mod = " (mod)" if data.get("distinguished") == "moderator" else ""
            reply = f", reply to {parent}" if parent else ""
            score = data.get("score")
            points = f", {score} point{'s' if score != 1 else ''}" if isinstance(score, int) else ""
            lines.append(f"- **{author}**{op}{mod} [→]({permalink(sub, post_id, data.get('id'))}) "
                         f"(depth {depth}{reply}{points}):" + item_text(body))
            count = 1
        for child in by_score(listing(data.get("replies"))):
            count += walk(child, depth + 1, author if alive else "[deleted]", lines)
        return count

    for thing in by_score(comments):
        lines: list[str] = []
        n = walk(thing, 0, None, lines)
        if not n:
            continue
        threads += 1
        total += n
        sections.append(f"### Thread {threads} ({n} comment{'s' if n != 1 else ''})\n\n" + "\n".join(lines))
    return "\n\n".join(sections), total, threads, more


# ---------------------------------------------------------------- post


def host(url: str | None) -> str:
    return re.sub(r"^www\.", "", (urllib.parse.urlsplit(url or "").hostname or "").lower())


def linked(post: dict) -> tuple[str | None, str | None]:
    """(the article URL of a link post, the media URL of an image/gallery/video post); a text post has neither."""
    url = post.get("url_overridden_by_dest") or post.get("url")
    h = host(url)
    if post.get("is_self") or not url or h == "reddit.com" or h.endswith(".reddit.com"):
        return None, None
    if post.get("is_video") or post.get("is_gallery") or post.get("post_hint") in ("image", "hosted:video") \
            or h in MEDIA_HOSTS or h.endswith(".redd.it"):
        return None, url
    return url, None


def iso(ts) -> str | None:
    return datetime.fromtimestamp(float(ts), timezone.utc).strftime("%Y-%m-%d") if ts else None


def render_content(meta: dict, extras: dict, post_md: str, article_md: str, discussion_md: str) -> str:
    ratio = extras.get("upvote_ratio")
    rows = [f"# {meta['title']}", "", f"- url: {meta['url']}"]
    for label, value in (("subreddit", f"r/{extras['subreddit']}"), ("posted by", meta.get("author")),
                         ("published", meta.get("published")),
                         ("score", extras.get("score") is not None and
                          f"{extras['score']} points" + (f" ({round(ratio * 100)}% upvoted)" if ratio else "")),
                         ("flair", extras.get("flair")), ("crossposted from", extras.get("crosspost_from")),
                         ("article", extras.get("article_url")), ("media", extras.get("media")),
                         ("comments", f"{extras['comments']} in {extras['threads']} threads"
                          + (f" ({extras['not_loaded']} more behind 'load more', not loaded)"
                             if extras.get("not_loaded") else "")),
                         ("article extractor", extras.get("article_extractor")
                          and f"{extras['article_extractor']} ({extras['article_words']} words)"),
                         ("archived copy", extras.get("snapshot")),
                         ("source", extras.get("api") == "arctic" and "the Arctic Shift archive"
                          + (" (the post is younger than ~36 h: scores and comments are still being archived)"
                             if extras.get("young") else ""))):
        if value:
            rows.append(f"- {label}: {value}")
    rows += ["", "## Post", "", post_md or "*No text: a link post.*", ""]
    if article_md:
        rows += ["## Article", "", article_md, ""]
    rows += ["## Discussion", "", discussion_md or "*No comments yet.*", ""]
    return "\n".join(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("post", help="a Reddit post, comment or share link, or the bare post id")
    ap.add_argument("--refresh", action="store_true", help="refetch the post even if it was prepared before")
    ap.add_argument("--no-article", action="store_true", help="only the post and the discussion, not a linked page")
    args = ap.parse_args(argv)

    r = route(f"https://redd.it/{args.post}" if re.fullmatch(r"[a-z0-9]{1,13}", args.post) else args.post)
    if r["source"] != "reddit":
        raise SkillError(f"{args.post} is a {r['source']} input, not a Reddit post")
    if r["kind"] == "share":
        final = resolve_share(r["url"])
        log(f"share link -> {final}")
        r = route(final)
    focus = r.get("comment")
    existing = find_by_id("reddit", r["id"])
    if existing and (existing / "content.md").exists() and not args.refresh:
        log(f"reusing: {existing} (pass --refresh to refetch)")
        return print_envelope(existing, read_json(existing / "metadata.json"), reused=True, focus=focus)

    attempts: list[str] = []
    post, comments, api = fetch_thread(r["id"], attempts)
    hn = hn_prepare()
    sub, post_id = post.get("subreddit") or r.get("subreddit") or "unknown", post.get("id") or r["id"]
    discussion_md, count, threads, more = discussion(comments, sub, post_id, hn.item_text)
    log(f"{api}: {count} comments in {threads} threads" + (f", {more} behind 'load more'" if more else ""))

    cross = (post.get("crosspost_parent_list") or [None])[0]
    body_post = cross or post  # a crosspost's text and link are its parent's
    article_url, media = linked(body_post)
    selftext = (body_post.get("selftext") or "").strip()
    if selftext not in GONE:
        post_md = f"**{post.get('author')}** [→]({REDDIT}/r/{sub}/comments/{post_id}/):" + hn.item_text(selftext)
    elif selftext:
        post_md = f"*The post's text was {selftext.strip('[]')}.*"
    else:
        post_md = "*Only a title.*" if body_post.get("is_self") else ""

    old = read_json(existing / "metadata.json") if existing else {}
    article_md, facts = "", {}
    if article_url and not args.no_article:
        log(f"article: {article_url}")
        article_md, facts = hn.article(article_url, attempts)
        if not facts and (kept := hn.old_article(existing, old)):
            log("keeping the article of the last run")
            article_md, facts = kept

    extras = {k: v for k, v in ({
        "subreddit": sub, "score": post.get("score"), "upvote_ratio": post.get("upvote_ratio"), "comments": count,
        "num_comments": post.get("num_comments"), "threads": threads, "not_loaded": more or None,
        "flair": post.get("link_flair_text"), "article_url": article_url, "media": media,
        "crosspost_from": cross and f"r/{cross.get('subreddit')}", "over_18": post.get("over_18") or None,
        "api": api, "attempts": attempts or None} | facts).items() if v is not None}
    young = api == "arctic" and time.time() - float(post.get("created_utc") or 0) < 36 * 3600
    meta = {
        "source": "reddit", "id": post_id, "url": f"{REDDIT}/r/{sub}/comments/{post_id}/",
        "title": (post.get("title") or f"Reddit post {post_id}").strip(), "author": post.get("author"),
        "published": iso(post.get("created_utc")), "fetched": datetime.now().isoformat(timespec="seconds"),
        "site": f"r/{sub}", "word_count": 0, "duration": None, "extractor": api, "content_file": "content.md",
        "extras": extras,
    }
    content = render_content(meta, extras | {"comments": count, "threads": threads, "young": young}, post_md,
                             article_md, discussion_md)
    meta["word_count"] = len(content.split())
    folder = existing or unique_dir(meta)
    folder.mkdir(parents=True, exist_ok=True)
    log(f"{'refreshing' if existing else 'folder'}: {folder}")
    (folder / "content.md").write_text(content, encoding="utf-8")
    meta = update_json(folder / "metadata.json", meta | {"prepared_at": old.get("prepared_at") or meta["fetched"]})
    return print_envelope(folder, meta, reused=bool(existing), focus=focus)


def print_envelope(folder: Path, meta: dict, reused: bool, focus: str | None = None) -> int:
    """The envelope; `focus_comment` is this run's comment link only (never stored: a later post link has none)."""
    extras = meta.get("extras") or {}
    print(json.dumps(envelope(folder, meta, "thread", reused=reused, subreddit=extras.get("subreddit"),
                              score=extras.get("score"), comments=extras.get("comments"),
                              threads=extras.get("threads"), not_loaded=extras.get("not_loaded"),
                              article_url=extras.get("article_url"), media=extras.get("media"),
                              focus_comment=focus, api=extras.get("api"), attempts=extras.get("attempts")),
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    run_main(main)

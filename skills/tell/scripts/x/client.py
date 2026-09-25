#!/usr/bin/env python3
"""X (Twitter) access for the x source, without login: the FxTwitter API v2 (api.fxtwitter.com, unofficial) and
X's embed endpoint (cdn.syndication.twimg.com) as the fallback for a single post.

- post(id): the post and its author chain from it on (FxTwitter's thread of a post starts at that post) from
  /2/thread/<id>; when FxTwitter fails, /2/status/<id>; when that fails too, the syndication endpoint
  (the post only, no thread, no replies). Every fallback is logged and noted in `attempts`.
- thread(id): post(id), plus the author's posts above it, walked up one light /2/status/<id> call each (at most
  MAX_UP; a longer chain is cut and noted).
- replies(id): the replies from /2/conversation/<id>, ranked by likes, then by recency for more (the two
  rankings overlap), following the cursor up to `limit`. FxTwitter sometimes answers an empty page or 404s a
  cursor: an empty first page is asked once more, a failed cursor ends that ranking (noted in `attempts`).
A deleted, suspended or protected post raises Unavailable (a SkillError) with the reason.

Usage: client.py <post id> [--replies N]   (prints {status, thread, replies, api, attempts} as JSON)
"""
from __future__ import annotations

import argparse
import html
import http.client
import json
import math
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

from _common import SkillError, log, run_main

FX = "https://api.fxtwitter.com/2/"
SYNDICATION = "https://cdn.syndication.twimg.com/tweet-result?id={id}&token={token}&lang=en"
TIMEOUT = 30
MAX_PAGES = 10  # per ranking
MAX_UP = 25  # thread posts above the linked one, fetched one /2/status call each
RANKINGS = ("likes", "recency")


class Unavailable(SkillError):
    """The post exists no more or cannot be read without login (deleted, suspended, protected)."""


class HTTPStatus(SkillError):
    """An HTTP error answer without a JSON body; `code` is the HTTP status."""

    def __init__(self, url: str, code: int):
        super().__init__(f"{url} answered HTTP {code}")
        self.code = code


def get_json(url: str) -> dict:
    """The JSON answer. FxTwitter answers errors as JSON too ({"code": 404, ...}): an HTTP error with a JSON body
    returns that body; anything else raises SkillError."""
    req = urllib.request.Request(url, headers={"User-Agent": "tell"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except (ValueError, OSError):
            body = None
        if isinstance(body, dict):
            return body | {"code": body.get("code") or e.code}
        raise HTTPStatus(url, e.code)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise SkillError(f"could not fetch {url}: {getattr(e, 'reason', e)}")
    except (http.client.HTTPException, ValueError):  # a cut-off answer, bad UTF-8 or JSON
        raise SkillError(f"{url} did not answer JSON")


def syndication_token(post_id: str) -> str:
    """The token X's embed script sends: `((id / 1e15) * Math.PI).toString(36)` without zeros and the dot. The
    fraction digits follow V8's shortest round-trip radix conversion (DoubleToRadixCString)."""
    value = int(post_id) / 1e15 * math.pi
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    whole, frac = int(value), value - int(value)
    delta = max(0.5 * (math.nextafter(value, math.inf) - value), math.nextafter(0.0, 1.0))
    out: list[int] = []
    if frac >= delta:
        while True:
            frac *= 36
            delta *= 36
            d = int(frac)
            out.append(d)
            frac -= d
            if (frac > 0.5 or (frac == 0.5 and d & 1)) and frac + delta > 1:
                while out and out[-1] + 1 >= 36:  # round up, carrying
                    out.pop()
                if out:
                    out[-1] += 1
                else:
                    whole += 1
                break
            if frac < delta:
                break
    head = ""
    while whole:
        whole, d = divmod(whole, 36)
        head = digits[d] + head
    text = (head or "0") + "." + "".join(digits[d] for d in out)
    return re.sub(r"0+|\.", "", text)


def tombstone(status: dict | None) -> str | None:
    """Why a post is unavailable, when FxTwitter answered a tombstone instead of the post."""
    if isinstance(status, dict) and status.get("type") == "tombstone":
        return status.get("message") or status.get("reason") or "unavailable"
    return None


def from_syndication(d: dict) -> dict:
    """A syndication answer in FxTwitter's v2 status shape (the fields prepare.py reads)."""
    user = d.get("user") or {}
    text = html.unescape(d.get("text") or "")  # the embed endpoint answers &amp; &lt; &gt;
    for u in (d.get("entities") or {}).get("urls") or []:  # t.co links -> the real URLs
        if u.get("url") and u.get("expanded_url"):
            text = text.replace(u["url"], u["expanded_url"])
    photos, videos = [], []
    for m in d.get("mediaDetails") or []:
        if m.get("type") == "photo":
            photos.append({"type": "photo", "url": m.get("media_url_https"), "altText": m.get("ext_alt_text")})
        elif m.get("type") in ("video", "animated_gif"):
            videos.append({"type": "video" if m["type"] == "video" else "gif", "url": m.get("expanded_url"),
                           "duration": ((m.get("video_info") or {}).get("duration_millis") or 0) / 1000})
        text = text.replace(m.get("url") or "\0", "").strip()  # the pic.x.com link of the media
    sid = d.get("id_str")
    name = user.get("screen_name")
    quoted = d.get("quoted_tweet")
    return {
        "type": "status", "id": sid, "url": f"https://x.com/{name or 'i'}/status/{sid}", "text": text,
        "created_at": d.get("created_at"), "created_timestamp": None,
        "likes": d.get("favorite_count"), "replies": d.get("conversation_count"), "reposts": None, "views": None,
        "author": {"screen_name": name, "name": user.get("name")},
        "media": {"photos": photos, "videos": videos} if photos or videos else {},
        "quote": from_syndication(quoted) if isinstance(quoted, dict) and quoted.get("id_str") else None,
        "community_note": None, "replying_to": (
            {"screen_name": d.get("in_reply_to_screen_name"), "status": d.get("in_reply_to_status_id_str")}
            if d.get("in_reply_to_status_id_str") else None),
    }


class FxTwitter:
    """The x source's API client. `get` (url -> dict) is injectable for the tests."""

    def __init__(self, get=None):
        self.get = get or get_json
        self.attempts: list[str] = []
        self.api = "fxtwitter"

    def note(self, msg: str) -> None:
        self.attempts.append(msg)
        log(msg)

    def thread(self, post_id: str) -> list[dict]:
        """The author's whole chain around a post, in order. FxTwitter's thread starts at the linked post when it
        sits inside a self-thread, so the posts above it are walked up, one /2/status call each (at most MAX_UP;
        a cut is noted), and put in front: exactly the path to the linked post, never another branch."""
        chain = self.post(post_id)[1]
        if self.api == "syndication":
            return chain
        seen = {str(s.get("id")) for s in chain}
        above: list[dict] = []
        while parent := self.parent_in_chain(above[0] if above else chain[0]):
            if parent in seen:  # a loop in the answers: stop
                break
            if len(above) >= MAX_UP:
                self.note(f"thread: cut at {MAX_UP} posts above the linked one; the thread starts earlier "
                          f"(post {parent})")
                break
            try:
                status = self.status(parent)
            except SkillError as e:
                self.note(f"thread: the post above {(above[0] if above else chain[0]).get('id')} could not be "
                          f"fetched ({e})")
                break
            seen.add(parent)
            above.insert(0, status)
        return above + chain

    @staticmethod
    def parent_in_chain(status: dict) -> str | None:
        """The id of the post this one answers when that is the author's own (the chain goes on above)."""
        up = status.get("replying_to") or {}
        author = (status.get("author") or {}).get("screen_name") or ""
        if up.get("status") and (up.get("screen_name") or "").lower() == author.lower():
            return str(up["status"])
        return None

    def status(self, post_id: str) -> dict:
        """One post from /2/status (no chain, no fallback); raises SkillError when FxTwitter has none."""
        d = self.get(f"{FX}status/{post_id}")
        status = d.get("status")
        if reason := tombstone(status):
            raise Unavailable(f"x.com post {post_id} is unavailable: {reason}")
        if not (isinstance(status, dict) and status.get("id")):
            raise SkillError(f"FxTwitter has no post {post_id} (code {d.get('code')})")
        return status

    def post(self, post_id: str, fallback: bool = True) -> tuple[dict, list[dict]]:
        """(the post, its thread: the author chain from the post on, the post included). Without `fallback`
        a failure raises instead of trying the embed endpoint (and `api` stays as it is)."""
        not_found = 0  # FxTwitter endpoints that answered "no such post" (not a failure to reach them)
        for endpoint in ("thread", "status"):
            try:
                d = self.get(f"{FX}{endpoint}/{post_id}")
            except SkillError as e:
                self.note(f"fxtwitter {endpoint}: failed ({e})")
                continue
            status = d.get("status")
            if reason := tombstone(status):
                raise Unavailable(f"x.com post {post_id} is unavailable: {reason}")
            if isinstance(status, dict) and status.get("id"):
                thread = [s for s in d.get("thread") or [] if isinstance(s, dict) and s.get("id")]
                return status, thread or [status]
            not_found += d.get("code") == 404
            self.note(f"fxtwitter {endpoint}: no post (code {d.get('code')})")
        if not fallback:
            raise SkillError(f"FxTwitter has no post {post_id}")
        self.note("-> falling back to X's embed endpoint (the post only: no thread, no replies)")
        try:
            d = self.get(SYNDICATION.format(id=post_id, token=syndication_token(post_id)))
        except HTTPStatus as e:
            if e.code == 404 and not_found == 2:  # a deleted post: 404 everywhere, no tombstone
                raise Unavailable(f"x.com post {post_id} is deleted or does not exist (FxTwitter: code 404, "
                                  f"X's embed endpoint: HTTP 404)")
            raise SkillError(f"x.com post {post_id} could not be fetched: FxTwitter and the embed endpoint "
                             f"failed ({e})")
        except SkillError as e:
            raise SkillError(f"x.com post {post_id} could not be fetched: FxTwitter and the embed endpoint "
                             f"failed ({e})")
        if d.get("__typename") == "TweetTombstone" or not d.get("id_str"):
            raise Unavailable(f"x.com post {post_id} is deleted, protected or does not exist")
        self.api = "syndication"
        status = from_syndication(d)
        return status, [status]

    def replies(self, post_id: str, limit: int, expected: int | None = None) -> list[dict]:
        """Up to `limit` replies below the post (any depth), each once, likes ranking first."""
        seen: dict[str, dict] = {}
        if self.api == "syndication" or limit <= 0:
            return []
        for ranking in RANKINGS:
            cursor, pages = None, 0
            while len(seen) < limit and pages < MAX_PAGES:
                page = self.page(post_id, ranking, cursor, expected, first=pages == 0)
                if page is None:
                    break
                pages += 1
                for r in page.get("replies") or []:
                    if isinstance(r, dict) and r.get("id") and r.get("type") != "tombstone":
                        seen.setdefault(r["id"], r)
                cursor = (page.get("cursor") or {}).get("bottom")
                if not cursor or not page.get("replies"):
                    break
            if len(seen) >= limit or (expected is not None and len(seen) >= expected):
                break
        return list(seen.values())[:limit]

    def page(self, post_id: str, ranking: str, cursor: str | None, expected: int | None,
             first: bool) -> dict | None:
        """One conversation page, or None when it failed (noted). An empty first page is asked twice."""
        url = f"{FX}conversation/{post_id}?ranking_mode={ranking}"
        if cursor:
            url += "&cursor=" + urllib.parse.quote(cursor, safe="")
        d: dict = {}
        for attempt in (1, 2):
            try:
                d = self.get(url)
            except SkillError as e:
                self.note(f"fxtwitter conversation ({ranking}): failed ({e})")
                return None
            if d.get("replies") or not first or not expected or attempt == 2:
                break
        if d.get("code") not in (None, 200):
            what = "the next page" if cursor else "the replies"
            self.note(f"fxtwitter conversation ({ranking}): {what} answered code {d.get('code')}")
            return None
        return d


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("post", help="the post id")
    ap.add_argument("--replies", type=int, default=0, help="also fetch up to N replies")
    args = ap.parse_args(argv)
    fx = FxTwitter()
    thread = fx.thread(args.post)
    status = next((s for s in thread if s.get("id") == args.post), thread[0])
    replies = fx.replies(args.post, args.replies, status.get("replies")) if args.replies else []
    print(json.dumps({"status": status, "thread": thread, "replies": replies, "api": fx.api,
                      "attempts": fx.attempts}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    run_main(main)

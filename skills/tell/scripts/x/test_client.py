#!/usr/bin/env python3
"""Unit tests for x/client.py (offline: recorded FxTwitter answers, urllib mocked)."""
import io
import json
import sys
import unittest
import urllib.error
from email.message import Message
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.append(str(HERE.parent / "shared"))

import client  # noqa: E402
from _common import SkillError  # noqa: E402
from fake_fx import FX, ROOT, SECOND, VIDEO, FakeGet, fake, load  # noqa: E402


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class TestGetJson(unittest.TestCase):
    def test_an_error_with_a_json_body_returns_the_body(self):
        body = io.BytesIO(b'{"status":null,"code":404}')
        err = urllib.error.HTTPError("u", 404, "nf", Message(), body)
        self.addCleanup(err.close)
        with mock.patch.object(client.urllib.request, "urlopen", side_effect=err):
            self.assertEqual(client.get_json("https://x.test/u"), {"status": None, "code": 404})

    def test_an_error_without_json_raises_with_its_status(self):
        err = urllib.error.HTTPError("u", 404, "nf", Message(), io.BytesIO(b""))  # the embed endpoint's 404
        self.addCleanup(err.close)
        with mock.patch.object(client.urllib.request, "urlopen", side_effect=err):
            with self.assertRaisesRegex(client.HTTPStatus, "HTTP 404") as ctx:
                client.get_json("https://x.test/u")
        self.assertEqual(ctx.exception.code, 404)

    def test_ok(self):
        with mock.patch.object(client.urllib.request, "urlopen", return_value=FakeResponse(b'{"code":200}')):
            self.assertEqual(client.get_json("https://x.test/u"), {"code": 200})


class TestSyndication(unittest.TestCase):
    def test_token_matches_the_embed_script(self):
        # node -e 'console.log(((Number(id)/1e15)*Math.PI).toString(36).replace(/(0+|\.)/g,""))'
        self.assertEqual(client.syndication_token(ROOT), "53ic2ru2c1i")

    def test_answer_in_the_v2_shape(self):
        s = client.from_syndication(load("syndication.json"))
        self.assertEqual((s["id"], s["author"]["screen_name"], s["likes"], s["replies"]),
                         (ROOT, "simonw", 662, 86))
        self.assertIn("https://simonwillison.net/2026/Sep/23/gemini-tts-playground/", s["text"])
        self.assertNotIn("t.co/", s["text"])
        self.assertEqual(s["url"], f"https://x.com/simonw/status/{ROOT}")

    def test_media_and_quote(self):
        d = load("syndication.json") | {
            "text": "look https://t.co/pic", "mediaDetails": [
                {"type": "photo", "media_url_https": "https://pbs.twimg.com/a.jpg", "url": "https://t.co/pic"},
                {"type": "video", "expanded_url": "https://x.com/simonw/status/1/video/1",
                 "video_info": {"duration_millis": 30500}}],
            "quoted_tweet": {"id_str": "5", "text": "quoted", "user": {"screen_name": "q"}}}
        s = client.from_syndication(d)
        self.assertEqual(s["text"], "look")
        self.assertEqual(s["media"]["photos"][0]["url"], "https://pbs.twimg.com/a.jpg")
        self.assertEqual(s["media"]["videos"][0]["duration"], 30.5)
        self.assertEqual((s["quote"]["id"], s["quote"]["author"]["screen_name"]), ("5", "q"))

    def test_entities_are_decoded(self):
        s = client.from_syndication(load("syndication.json") | {"text": "a &amp; b &lt;3 &gt; c", "entities": {}})
        self.assertEqual(s["text"], "a & b <3 > c")


class TestPost(unittest.TestCase):
    def test_thread(self):
        fx = fake()
        status, thread = fx.post(ROOT)
        self.assertEqual(status["id"], ROOT)
        self.assertEqual([s["id"] for s in thread], [ROOT, SECOND])
        self.assertEqual((fx.api, fx.attempts), ("fxtwitter", []))

    def test_thread_walks_up_to_the_first_post(self):
        fx = fake()
        self.assertEqual([s["id"] for s in fx.thread(SECOND)], [ROOT, SECOND])
        # one light status call per post above; no chain is downloaded twice
        self.assertEqual(fx.get.calls, [f"{FX}thread/{SECOND}", f"{FX}status/{ROOT}"])
        self.assertEqual([s["id"] for s in fx.thread(ROOT)], [ROOT, SECOND])
        self.assertEqual(fx.attempts, [])

    def chain(self, n: int, extra: dict | None = None) -> dict:
        """Answers for a self-thread p1 <- p2 <- ... <- pn by @a (FxTwitter's thread of pn is [pn])."""
        posts = [{"id": f"p{i}", "author": {"screen_name": "a"},
                  "replying_to": {"screen_name": "A", "status": f"p{i - 1}"} if i > 1 else None}
                 for i in range(1, n + 1)]
        answers = {f"{FX}status/{p['id']}": {"code": 200, "status": p} for p in posts}
        return answers | {f"{FX}thread/p{n}": {"code": 200, "status": posts[-1], "thread": [posts[-1]]}} | (extra or {})

    def test_a_long_walk_is_cut_and_noted(self):
        fx = fake(self.chain(6))
        with mock.patch.object(client, "MAX_UP", 3):
            thread = fx.thread("p6")
        self.assertEqual([s["id"] for s in thread], ["p3", "p4", "p5", "p6"])
        self.assertIn("cut at 3 posts", fx.attempts[-1])
        self.assertIn("(post p2)", fx.attempts[-1])

    def test_the_walk_takes_only_the_path_and_stops_on_a_loop(self):
        # p1's own thread is another branch (p1 -> b2); it is never fetched or spliced in
        branch = {f"{FX}thread/p1": {"code": 200, "status": {"id": "p1"}, "thread": [{"id": "p1"}, {"id": "b2"}]}}
        fx = fake(self.chain(3, branch))
        self.assertEqual([s["id"] for s in fx.thread("p3")], ["p1", "p2", "p3"])
        self.assertNotIn(f"{FX}thread/p1", fx.get.calls)
        loop = self.chain(2)
        loop[f"{FX}status/p1"]["status"] = loop[f"{FX}status/p1"]["status"] | {
            "replying_to": {"screen_name": "a", "status": "p2"}}
        fx = fake(loop)
        self.assertEqual([s["id"] for s in fx.thread("p2")], ["p1", "p2"])

    def test_a_missing_post_above_is_noted(self):
        answers = self.chain(3)
        del answers[f"{FX}status/p1"]
        fx = fake(answers)
        self.assertEqual([s["id"] for s in fx.thread("p3")], ["p2", "p3"])
        self.assertIn("the post above p2 could not be fetched", fx.attempts[-1])

    def test_thread_stops_at_a_reply_to_someone_else(self):
        reply = load("conversation.likes.json")["replies"][1]  # @dr_nikhilshah's reply to simonw
        fx = fake({f"{FX}thread/{reply['id']}": {"code": 200, "status": reply, "thread": [reply]}})
        self.assertEqual([s["id"] for s in fx.thread(reply["id"])], [reply["id"]])

    def test_status_endpoint_when_the_thread_fails(self):
        video = load("status.video.json")
        fx = fake({f"{FX}thread/{VIDEO}": SkillError("timeout"), f"{FX}status/{VIDEO}": video})
        status, thread = fx.post(VIDEO)
        self.assertEqual([s["id"] for s in thread], [VIDEO])
        self.assertEqual(fx.attempts, ["fxtwitter thread: failed (timeout)"])

    def test_embed_fallback_when_fxtwitter_has_nothing(self):
        synd = load("syndication.json")
        fx = fake({f"{FX}thread/{ROOT}": None, f"{FX}status/{ROOT}": None,
                   client.SYNDICATION.format(id=ROOT, token=client.syndication_token(ROOT)): synd})
        status, thread = fx.post(ROOT)
        self.assertEqual((status["id"], fx.api), (ROOT, "syndication"))
        self.assertIn("embed endpoint", fx.attempts[-1])
        self.assertEqual(fx.replies(ROOT, 50), [])  # the embed endpoint has no replies

    def test_tombstone(self):
        tomb = {"code": 200, "status": {"type": "tombstone", "reason": "private", "message": "protected account"}}
        with self.assertRaisesRegex(client.Unavailable, "protected account"):
            fake({f"{FX}thread/1": tomb}).post("1")

    def test_a_deleted_post(self):
        # FxTwitter answers {"status": null, "code": 404} on both endpoints, the embed endpoint HTTP 404 with an
        # empty body (no tombstone) -- recorded 2026-09-25
        fx = fake()
        with self.assertRaisesRegex(client.Unavailable, "deleted or does not exist"):
            fx.post("2102861892549279999")
        self.assertEqual(fx.api, "fxtwitter")  # the fallback did not answer: not switched

    def test_unreachable_is_not_called_deleted(self):
        down = SkillError("timeout")
        fx = fake({f"{FX}thread/5": down, f"{FX}status/5": down,
                   client.SYNDICATION.format(id="5", token=client.syndication_token("5")): down})
        with self.assertRaises(SkillError) as ctx:
            fx.post("5")
        self.assertNotIsInstance(ctx.exception, client.Unavailable)
        self.assertIn("could not be fetched", str(ctx.exception))

    def test_without_fallback_the_api_stays(self):
        fx = fake()
        with self.assertRaisesRegex(SkillError, "FxTwitter has no post"):
            fx.post("404", fallback=False)
        self.assertEqual(fx.api, "fxtwitter")
        self.assertFalse(any("syndication" in u for u in fx.get.calls))


class TestReplies(unittest.TestCase):
    def test_both_rankings_merged_and_the_404_cursor_noted(self):
        fx = fake()
        replies = fx.replies(ROOT, 200, 86)
        likes = {r["id"] for r in load("conversation.likes.json")["replies"]}
        recency = {r["id"] for r in load("conversation.recency.json")["replies"]}
        self.assertEqual({r["id"] for r in replies}, likes | recency)
        self.assertEqual(len(replies), len(likes | recency))
        self.assertTrue(all("next page answered code 404" in a for a in fx.attempts))

    def test_limit(self):
        fx = fake()
        self.assertEqual(len(fx.replies(ROOT, 5, 86)), 5)
        self.assertFalse(any("recency" in u for u in fx.get.calls))  # the likes page was enough

    def test_an_empty_first_page_is_asked_again(self):
        pages = iter([{"code": 200, "replies": None}, load("conversation.likes.json")])
        get = FakeGet({f"{FX}conversation/{ROOT}?ranking_mode=likes": lambda: next(pages)})
        replies = client.FxTwitter(get=get).replies(ROOT, 10, 86)
        self.assertEqual(len(replies), 10)
        self.assertEqual(sum("ranking_mode=likes" in u and "cursor" not in u for u in get.calls), 2)

    def test_a_failing_conversation_is_noted(self):
        fx = fake({f"{FX}conversation/{ROOT}?ranking_mode=likes": SkillError("down"),
                   f"{FX}conversation/{ROOT}?ranking_mode=recency": {"code": 404}})
        self.assertEqual(fx.replies(ROOT, 10, 86), [])
        self.assertEqual(len(fx.attempts), 2)


class TestMain(unittest.TestCase):
    def test_prints_the_thread(self):
        out = io.StringIO()
        with mock.patch.object(client, "get_json", FakeGet()), mock.patch("sys.stdout", out):
            client.main([SECOND])
        d = json.loads(out.getvalue())
        self.assertEqual((d["status"]["id"], len(d["thread"]), d["replies"]), (SECOND, 2, []))


if __name__ == "__main__":
    unittest.main()

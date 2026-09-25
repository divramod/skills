#!/usr/bin/env python3
"""Unit tests for reddit/prepare.py (offline: recorded Arctic Shift JSON, the article extractor mocked)."""
import copy
import io
import json
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import prepare  # noqa: E402  (reddit/prepare.py: this folder comes first)
from _common import CONTRACT_KEYS, ENVELOPE_KEYS, SkillError, read_json  # noqa: E402
from extract import Extraction, Page  # noqa: E402

FIXTURES = HERE / "fixtures"
LINK = json.loads((FIXTURES / "link.arctic.json").read_text())  # r/programming, a link post, 9 comments
SELF = json.loads((FIXTURES / "self.arctic.json").read_text())  # r/AskProgramming, a text post
ARTICLE = LINK["post"]["url"]
BLOCKED = SkillError("https://www.reddit.com/comments/x/.json answered HTTP 403")


def reddit_json(fixture: dict, more: int = 0) -> list:
    """The fixture in the shape of Reddit's own /comments/<id>.json (optionally with a "load more" stub)."""
    tree = copy.deepcopy(fixture["tree"])
    if more:
        tree.append({"kind": "more", "data": {"count": more, "children": ["a"] * more}})
    return [{"kind": "Listing", "data": {"children": [{"kind": "t3", "data": copy.deepcopy(fixture["post"])}]}},
            {"kind": "Listing", "data": {"children": tree}}]


def api(reddit=None, oauth=None, token=None, arctic=None):
    """A fake get_json: each API answers its value, or raises it when it is an exception (default: blocked)."""
    calls = []

    def get(url, headers=None, data=None):
        calls.append(url)
        if url.startswith(prepare.TOKEN):
            answer = token
        elif url.startswith(prepare.OAUTH):
            answer = oauth
        elif url.startswith(prepare.REDDIT):
            answer = reddit
        else:
            key = "tree" if "/comments/tree" in url else "post"
            answer = arctic and ({"data": copy.deepcopy(arctic["tree"])} if key == "tree" else
                                 {"data": [copy.deepcopy(arctic["post"])]})
        if isinstance(answer, Exception) or answer is None:
            raise answer if isinstance(answer, Exception) else BLOCKED
        return answer
    get.calls = calls
    return get


def article_page() -> Page:
    md = "# Data races\n\nThreadSanitizer finds " + "races " * 300 + "\n\n## Go\n\nFast."
    return Page(Extraction(md, {"title": "Data races"}, "defuddle"), ["defuddle: x"], ARTICLE)


def quiet():
    return mock.patch.object(prepare, "log")


class TestFetch(unittest.TestCase):
    def test_reddit_answers_first(self):
        attempts = []
        with mock.patch.object(prepare, "get_json", api(reddit=reddit_json(LINK))), quiet():
            post, comments, source = prepare.fetch_thread("1wexekt", attempts)
        self.assertEqual((post["id"], len(comments), source, attempts), ("1wexekt", len(LINK["tree"]), "reddit", []))

    def test_blocked_without_credentials_falls_back_to_the_archive(self):
        attempts = []
        with mock.patch.dict(os.environ, {}, clear=True), quiet(), \
                mock.patch.object(prepare, "get_json", api(arctic=LINK)):
            post, comments, source = prepare.fetch_thread("1wexekt", attempts)
        self.assertEqual((source, post["subreddit"]), ("arctic", "programming"))
        self.assertEqual(attempts, [f"reddit: {BLOCKED}",
                                    "oauth: skipped (REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not set)"])

    def test_credentials_use_an_app_token(self):
        get = api(token={"access_token": "t"}, oauth=reddit_json(SELF))
        with mock.patch.dict(os.environ, {"REDDIT_CLIENT_ID": "i", "REDDIT_CLIENT_SECRET": "s"}), quiet(), \
                mock.patch.object(prepare, "get_json", get):
            _, _, source = prepare.fetch_thread("1wgae8i", [])
        self.assertEqual(source, "oauth")
        self.assertTrue(get.calls[1].startswith(prepare.TOKEN))

    def test_nothing_answers_names_the_fix(self):
        with mock.patch.dict(os.environ, {}, clear=True), quiet(), mock.patch.object(prepare, "get_json", api()), \
                self.assertRaisesRegex(SkillError, "no API answered.*REDDIT_CLIENT_ID.*prefs/apps"):
            prepare.fetch_thread("1wexekt", [])

    def test_the_archive_is_asked_again_when_busy(self):
        answers = [SkillError("…/posts/ids answered HTTP 422"), {"data": [1]}]

        def get(url, headers=None, data=None):
            answer = answers.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return answer
        with mock.patch.object(prepare, "get_json", get), mock.patch.object(prepare, "RETRY_WAIT", 0), quiet():
            self.assertEqual(prepare.arctic("posts/ids?ids=x"), {"data": [1]})
        with mock.patch.object(prepare, "get_json", mock.Mock(side_effect=SkillError("HTTP 404"))), quiet(), \
                self.assertRaisesRegex(SkillError, "404"):
            prepare.arctic("posts/ids?ids=x")  # not busy: no second try

    def test_archived_text_is_unescaped(self):
        thing = {"data": {"body": "a &amp; b &gt; c", "replies": {"data": {"children": [
            {"kind": "t1", "data": {"body": "&lt;x&gt;", "replies": ""}}]}}}}
        prepare.unescape(thing)
        self.assertEqual(thing["data"]["body"], "a & b > c")
        self.assertEqual(thing["data"]["replies"]["data"]["children"][0]["data"]["body"], "<x>")


class TestDiscussion(unittest.TestCase):
    def render(self, comments):
        return prepare.discussion(comments, "programming", "p1", prepare.hn_prepare().item_text)

    def test_threads_best_first_with_op_score_and_permalinks(self):
        md, count, threads, more = self.render(reddit_json(LINK, more=3)[1]["data"]["children"])
        self.assertEqual((count, threads, more), (9, 4, 3))
        self.assertTrue(md.startswith("### Thread 1 (4 comments)\n\n- **BenchEmbarrassed7316** "
                                      "[→](https://www.reddit.com/r/programming/comments/p1/_/p9is1t8/) "
                                      "(depth 0, 13 points):"))
        self.assertIn("(depth 1, reply to BenchEmbarrassed7316, 5 points): So much for Go", md)

    def test_deleted_comments_are_dropped_and_their_replies_kept(self):
        tree = [{"kind": "t1", "data": {"id": "a", "author": "[deleted]", "body": "[removed]", "score": 5,
                                        "replies": {"data": {"children": [
                                            {"kind": "t1", "data": {"id": "b", "author": "op", "body": "still here",
                                                                    "score": 1, "is_submitter": True,
                                                                    "replies": ""}}]}}}},
                {"kind": "t1", "data": {"id": "c", "author": "mod", "body": "Rule 3.", "score": 1,
                                        "distinguished": "moderator", "replies": ""}}]
        md, count, threads, _ = self.render(tree)
        self.assertEqual((count, threads), (2, 2))
        self.assertIn("- **op** (OP) [→](https://www.reddit.com/r/programming/comments/p1/_/b/) "
                      "(depth 1, reply to [deleted], 1 point): still here", md)
        self.assertIn("- **mod** (mod) [→]", md)
        self.assertNotIn("[removed]", md)


class TestLinked(unittest.TestCase):
    def test_article_media_and_text_posts(self):
        self.assertEqual(prepare.linked(LINK["post"]), (ARTICLE, None))
        self.assertEqual(prepare.linked(SELF["post"]), (None, None))
        video = {"is_self": False, "is_video": True, "url": "https://v.redd.it/abc"}
        self.assertEqual(prepare.linked(video), (None, "https://v.redd.it/abc"))
        image = {"is_self": False, "url": "https://i.redd.it/x.jpg"}
        self.assertEqual(prepare.linked(image), (None, "https://i.redd.it/x.jpg"))
        inner = {"is_self": False, "url": "https://www.reddit.com/r/a/comments/b/"}
        self.assertEqual(prepare.linked(inner), (None, None))


class TestMain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        env = mock.patch.dict(os.environ, {"TELL_ROOT": self.tmp.name}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(self.tmp.cleanup)

    def run_main(self, *args, get=None):
        out = io.StringIO()
        extract = mock.MagicMock(return_value=article_page())
        with mock.patch.object(prepare, "get_json", get or api(arctic=LINK)), \
                mock.patch.object(prepare.hn_prepare(), "extract", extract), quiet(), \
                mock.patch.object(prepare.hn_prepare(), "log"), redirect_stdout(out):
            self.assertEqual(prepare.main(list(args)), 0)
        return json.loads(out.getvalue()), extract

    def test_link_post_folder_content_and_contract(self):
        env, ex = self.run_main("https://old.reddit.com/r/programming/comments/1wexekt/data_races/")
        ex.assert_called_once_with(ARTICLE)
        folder = self.root / "discussions" / "reddit" / "programming" / (
            "data-races-and-the-limits-of-threadsanitizer-in-c-and-go-1wexekt")
        self.assertEqual(env["dir"], str(folder))
        self.assertTrue(set(ENVELOPE_KEYS) <= set(env))
        self.assertEqual((env["source"], env["kind"], env["comments"], env["score"], env["api"]),
                         ("reddit", "thread", 9, 70, "arctic"))
        meta = read_json(folder / "metadata.json")
        self.assertTrue(set(CONTRACT_KEYS) <= set(meta))
        self.assertEqual((meta["id"], meta["published"], meta["author"], meta["site"], meta["url"]),
                         ("1wexekt", "2026-09-13", "mttd", "r/programming",
                          "https://www.reddit.com/r/programming/comments/1wexekt/"))
        content = (folder / "content.md").read_text()
        for part in ("- subreddit: r/programming\n", "- score: 70 points (86% upvoted)\n", "- comments: 9 in 4 threads",
                     "## Post\n\n*No text: a link post.*", "## Article\n\n### Data races\n",
                     "## Discussion\n\n### Thread 1 (4 comments)", "- source: the Arctic Shift archive\n"):
            self.assertIn(part, content)

    def test_text_post_has_no_article(self):
        env, ex = self.run_main("https://redd.it/1wgae8i", get=api(reddit=reddit_json(SELF)))
        ex.assert_not_called()
        content = Path(env["content_file"]).read_text()
        self.assertIn("## Post\n\n**", content)
        self.assertIn("I am 23 yo and I work full time", content)
        self.assertNotIn("## Article", content)
        self.assertNotIn("Arctic Shift", content)
        self.assertIn("/discussions/reddit/askprogramming/", env["dir"])

    def test_comment_link_focuses_and_the_post_is_reused(self):
        env, _ = self.run_main("https://www.reddit.com/r/programming/comments/1wexekt/x/p9is1t8/")
        self.assertEqual((env["id"], env["focus_comment"]), ("1wexekt", "p9is1t8"))
        again, ex = self.run_main("1wexekt")
        ex.assert_not_called()
        self.assertEqual((again["dir"], again["reused"], again["focus_comment"]), (env["dir"], True, None))
        self.assertNotIn("focus_comment", read_json(Path(env["dir"]) / "metadata.json")["extras"])
        refreshed, ex = self.run_main("1wexekt", "--refresh", "--no-article")
        ex.assert_not_called()
        self.assertEqual((refreshed["dir"], refreshed["reused"]), (env["dir"], True))

    def test_share_link_is_resolved_first(self):
        final = "https://www.reddit.com/r/programming/comments/1wexekt/data_races/"
        with mock.patch.object(prepare, "resolve_share", return_value=final) as resolve:
            env, _ = self.run_main("https://www.reddit.com/r/programming/s/AbC123")
        resolve.assert_called_once_with("https://www.reddit.com/r/programming/s/AbC123")
        self.assertEqual(env["id"], "1wexekt")

    def test_a_young_archived_post_says_its_scores_are_settling(self):
        young = copy.deepcopy(LINK)
        young["post"]["created_utc"] = int(time.time()) - 3600
        env, _ = self.run_main("1wexekt", "--no-article", get=api(arctic=young))
        self.assertIn("younger than ~36 h", Path(env["content_file"]).read_text())

    def test_other_sources_are_refused(self):
        with self.assertRaisesRegex(SkillError, "not a Reddit post"):
            prepare.main(["https://news.ycombinator.com/item?id=1"])


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Unit tests for hn/prepare.py (offline: recorded Algolia/Firebase JSON, the article extractor mocked)."""
import copy
import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import prepare  # noqa: E402  (hn/prepare.py: this folder comes first)
from _common import CONTRACT_KEYS, ENVELOPE_KEYS, SkillError, read_json  # noqa: E402
from extract import Extraction, NotAPage, Page  # noqa: E402

FIXTURES = HERE / "fixtures"
SMALL = json.loads((FIXTURES / "small.algolia.json").read_text())
BIG = json.loads((FIXTURES / "big.algolia.json").read_text())
ASK = json.loads((FIXTURES / "ask.algolia.json").read_text())
KIDS = json.loads((FIXTURES / "small.firebase.json").read_text())["kids"]
STORY = 42457213
ARTICLE = "https://genesis-world.readthedocs.io/en/latest/"


def api(algolia: dict | None = None, firebase: dict | None = None):
    """A fake get_json over canned Algolia items (by id) and Firebase items (by id)."""
    algolia, firebase = algolia or {}, firebase or {}
    calls = []

    def get(url):
        calls.append(url)
        m = re.search(r"/(\d+)(?:\.json)?$", url)
        item_id = int(m.group(1))
        table = firebase if url.startswith(prepare.FIREBASE) else algolia
        result = table.get(item_id)
        if isinstance(result, Exception):
            raise result
        if result is None:
            raise SkillError(f"{url} answered HTTP 404")
        return result
    get.calls = calls
    return get


def article_page(words: int = 300) -> Page:
    md = "# Genesis World\n\nGenesis is a physics platform " + "for robots " * words + "\n\n## Features\n\nFast."
    return Page(Extraction(md, {"title": "Genesis World"}, "trafilatura"), ["trafilatura: x"], ARTICLE)


class TestCommentText(unittest.TestCase):
    def test_html_to_markdown(self):
        raw = ('First &amp; <i>foremost</i>:<p>see <a href="https:&#x2F;&#x2F;x.com&#x2F;a&#x2F;status&#x2F;1" '
               'rel="nofollow">https:&#x2F;&#x2F;x.com&#x2F;a&#x2F;status&#x2F;1</a> and '
               '<a href="https://example.com/long/path">the paper</a><p>&gt; quoted line'
               '<p><pre><code>  def f():\n      return 1\n</code></pre>')
        self.assertEqual(prepare.comment_text(raw),
                         "First & *foremost*:\n\nsee https://x.com/a/status/1 and [the paper](https://example.com/long/path)"
                         "\n\n> quoted line\n\n```\n  def f():\n      return 1\n```")

    def test_shortened_link_text_uses_the_href(self):
        raw = '<a href="https://example.com/a/very/long/path/to/page">https://example.com/a/very/long/...</a>'
        self.assertEqual(prepare.comment_text(raw), "https://example.com/a/very/long/path/to/page")


class TestDiscussion(unittest.TestCase):
    def test_threads_follow_hn_ranking_and_count_every_comment(self):
        md, comments, threads = prepare.discussion(SMALL, KIDS)
        self.assertEqual((comments, threads), (52, len(SMALL["children"])))
        first = re.findall(r"^- \*\*\S+\*\* \[→\]\(https://news\.ycombinator\.com/item\?id=(\d+)\) \(depth 0\)",
                           md, re.M)
        ranked = [k for k in KIDS if str(k) in first]
        self.assertEqual([int(i) for i in first], ranked)
        self.assertTrue(md.startswith("### Thread 1 ("))

    def test_replies_name_their_parent_and_depth(self):
        md, _, _ = prepare.discussion(SMALL, KIDS)
        self.assertRegex(md, r"\(depth 1, reply to \S+\): ")

    def test_deleted_comment_dropped_replies_kept(self):
        tree = {"id": 1, "children": [{"id": 2, "author": None, "text": None, "created_at_i": 1, "children": [
            {"id": 3, "author": "bob", "text": "still here", "created_at_i": 2, "children": []}]},
            {"id": 4, "author": None, "text": None, "created_at_i": 3, "children": []}]}
        md, comments, threads = prepare.discussion(tree, [])
        self.assertEqual((comments, threads), (1, 1))
        self.assertIn("- **bob** [→](https://news.ycombinator.com/item?id=3) (depth 1, reply to [deleted]): still here",
                      md)

    def test_comment_starting_with_code_puts_the_fence_on_its_own_line(self):
        tree = {"id": 1, "children": [{"id": 2, "author": "a", "text": "<pre><code>x = 1\n</code></pre>ok",
                                       "children": []}]}
        md, _, _ = prepare.discussion(tree, [])
        self.assertTrue(md.endswith("(depth 0):\n  ```\n  x = 1\n  ```\n\n  ok"), md)

    def test_link_text_brackets_are_escaped(self):
        self.assertEqual(prepare.comment_text('<a href="https://e.com/p">see [1] here</a>'),
                         "[see \\[1\\] here](https://e.com/p)")

    def test_multi_paragraph_comment_stays_in_its_list_item(self):
        tree = {"id": 1, "children": [{"id": 2, "author": "a", "text": "one<p>two", "children": []}]}
        md, _, _ = prepare.discussion(tree, [])
        self.assertTrue(md.endswith("(depth 0): one\n\n  two"))

    def test_big_thread(self):
        md, comments, threads = prepare.discussion(BIG, [])
        self.assertEqual(comments, 377)
        self.assertEqual(len(re.findall(r"^### Thread \d+", md, re.M)), threads)
        self.assertEqual(len(re.findall(r"^- \*\*", md, re.M)), comments)


class TestDemote(unittest.TestCase):
    def test_headings_move_below_article_code_untouched(self):
        self.assertEqual(prepare.demote("# A\n\n```\n# comment\n```\n\n###### F"),
                         "### A\n\n```\n# comment\n```\n\n###### F")


class TestFirebase(unittest.TestCase):
    def test_fallback_walks_the_tree(self):
        fb = {7: {"id": 7, "type": "story", "title": "T", "by": "op", "kids": [9, 8], "time": 1700000000},
              8: {"id": 8, "type": "comment", "by": "a", "text": "hi", "parent": 7, "kids": [10], "time": 2},
              9: {"id": 9, "type": "comment", "deleted": True, "parent": 7, "time": 3},
              10: {"id": 10, "type": "comment", "by": "b", "text": "yo", "parent": 8, "time": 4}}
        get = api({7: SkillError("algolia down")}, fb)
        attempts = []
        with mock.patch.object(prepare, "get_json", get), mock.patch.object(prepare, "log"):
            story, tree, source, focus = prepare.find_story(7, attempts)
            tree, source, ranks = prepare.load_tree(story, tree, source, attempts)
        self.assertEqual((story, source, focus, attempts), (7, "firebase", None, ["algolia: failed (algolia down)"]))
        self.assertEqual(ranks, [9, 8])
        md, comments, threads = prepare.discussion(tree, ranks)
        self.assertEqual((comments, threads), (2, 1))
        self.assertIn("(depth 1, reply to a): yo", md)

    def test_comment_resolves_to_its_story_via_parents(self):
        fb = {8: {"id": 8, "type": "comment", "by": "a", "text": "x", "parent": 7},
              7: {"id": 7, "type": "story", "title": "T", "kids": [8]}}
        with mock.patch.object(prepare, "get_json", api({}, fb)), mock.patch.object(prepare, "log"):
            story, tree, source, focus = prepare.find_story(8, [])
        self.assertEqual((story, tree, source, focus), (7, None, "firebase", 8))

    def test_poll_option_resolves_to_its_poll(self):
        fb = {8: {"id": 8, "type": "pollopt", "poll": 7}, 7: {"id": 7, "type": "poll", "title": "T"}}
        with mock.patch.object(prepare, "get_json", api({}, fb)), mock.patch.object(prepare, "log"):
            self.assertEqual(prepare.find_story(8, [])[0], 7)

    def test_missing_parent_is_an_error_not_a_crash(self):
        fb = {8: {"id": 8, "type": "comment", "by": "a", "text": "x", "parent": 7}, 7: None}
        with mock.patch.object(prepare, "get_json", lambda url: fb.get(int(re.search(r"(\d+)\.json", url)[1]))):
            with self.assertRaisesRegex(SkillError, "could not find the story of item 8"):
                prepare.story_of(prepare.from_firebase(fb[8]))

    def test_a_failing_comment_is_left_out_not_fatal(self):
        fb = {7: {"id": 7, "type": "story", "kids": [8, 9]}, 8: SkillError("HTTP 500"),
              9: {"id": 9, "type": "comment", "by": "b", "text": "yo", "parent": 7}}
        attempts = []
        with mock.patch.object(prepare, "get_json", api({}, fb)), mock.patch.object(prepare, "log"):
            tree = prepare.firebase_tree(7, attempts)
        self.assertEqual([c["id"] for c in tree["children"]], [9])
        self.assertIn("firebase: 1 comments could not be fetched", attempts[0])

    def test_lagging_algolia_falls_back_to_firebase(self):
        algolia = {"id": 7, "type": "story", "children": [{"id": 8, "author": "a", "text": "hi", "children": []}]}
        fb = {7: {"id": 7, "type": "story", "kids": [8, 9], "descendants": 40},
              8: {"id": 8, "type": "comment", "by": "a", "text": "hi", "parent": 7},
              9: {"id": 9, "type": "comment", "by": "b", "text": "new", "parent": 7}}
        attempts = []
        with mock.patch.object(prepare, "get_json", api({7: algolia}, fb)), mock.patch.object(prepare, "log"):
            tree, source, ranks = prepare.load_tree(7, algolia, "algolia", attempts)
        self.assertEqual((source, len(tree["children"]), ranks), ("firebase", 2, [8, 9]))
        self.assertEqual(attempts, ["algolia: lags behind (1 of 40 comments)"])


class TestMain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        env = mock.patch.dict(os.environ, {"TELL_ROOT": self.tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(self.tmp.cleanup)
        comment = {"id": 42460143, "type": "comment", "story_id": STORY, "author": "x", "text": "Agreed.",
                   "children": []}
        ask = copy.deepcopy(ASK)
        self.get = api({STORY: SMALL, 42460143: comment, ASK["id"]: ask},
                       {STORY: {"id": STORY, "kids": KIDS}, ASK["id"]: {"id": ASK["id"], "kids": []}})

    def run_main(self, *args, page=None):
        out = io.StringIO()
        extract = mock.MagicMock(side_effect=page if isinstance(page, Exception) else None,
                                 return_value=page or article_page())
        with mock.patch.object(prepare, "get_json", self.get), mock.patch.object(prepare, "extract", extract), \
                mock.patch.object(prepare, "log"), redirect_stdout(out):
            self.assertEqual(prepare.main(list(args)), 0)
        return json.loads(out.getvalue()), extract

    def test_link_post_folder_content_and_contract(self):
        env, ex = self.run_main(f"https://news.ycombinator.com/item?id={STORY}")
        ex.assert_called_once_with(ARTICLE)
        folder = self.root / "discussions" / "hn" / (
            "genesis-a-generative-physics-engine-for-general-purpose-robo-42457213")
        self.assertEqual(env["dir"], str(folder))
        self.assertTrue(set(ENVELOPE_KEYS) <= set(env))
        self.assertEqual((env["source"], env["kind"], env["comments"], env["points"]), ("hn", "thread", 52, 233))
        meta = read_json(folder / "metadata.json")
        self.assertTrue(set(CONTRACT_KEYS) <= set(meta))
        self.assertEqual((meta["id"], meta["published"], meta["author"], meta["extractor"]),
                         (str(STORY), "2024-12-19", "tomp", "algolia"))
        content = (folder / "content.md").read_text()
        self.assertIn("## Article\n\n### Genesis World\n", content)  # the article's h1 below ## Article
        self.assertIn(f"[¶1]({ARTICLE}#:~:text=", content)
        self.assertIn("#### Features", content)
        self.assertIn("## Discussion\n\n### Thread 1 (", content)
        self.assertIn("- comments: 52 in ", content)

    def test_comment_link_prepares_the_story_and_reuses_it(self):
        env, _ = self.run_main("42460143")
        self.assertEqual((env["id"], env["focus_comment"]), (str(STORY), 42460143))
        again, ex = self.run_main(f"https://news.ycombinator.com/item?id={STORY}")
        ex.assert_not_called()
        self.assertEqual((again["dir"], again["reused"], again["focus_comment"]), (env["dir"], True, None))
        focus, _ = self.run_main("42460143")
        self.assertEqual((focus["reused"], focus["focus_comment"]), (True, 42460143))
        self.assertNotIn("focus_comment", read_json(Path(env["dir"]) / "metadata.json")["extras"])

    def test_refresh_refetches(self):
        first, _ = self.run_main(str(STORY))
        second, ex = self.run_main(str(STORY), "--refresh")
        ex.assert_called_once()
        self.assertEqual((second["dir"], second["reused"]), (first["dir"], True))

    def test_refresh_keeps_a_good_article_when_extraction_fails(self):
        first, _ = self.run_main(str(STORY))
        second, _ = self.run_main(str(STORY), "--refresh", page=SkillError("blocked"))
        content = Path(second["content_file"]).read_text()
        self.assertIn("## Article\n\n### Genesis World\n", content)
        self.assertNotIn("could not be extracted", content)
        self.assertEqual(read_json(Path(second["dir"]) / "metadata.json")["extras"]["article_extractor"],
                         "trafilatura")

    def test_show_hn_keeps_the_post_text_before_the_article(self):
        show = copy.deepcopy(SMALL) | {"text": "I built this over a year."}
        self.get = api({STORY: show}, {STORY: {"id": STORY, "kids": KIDS}})
        env, ex = self.run_main(str(STORY))
        ex.assert_called_once()
        self.assertRegex(Path(env["content_file"]).read_text(),
                         r"## Article\n\n\*\*tomp\*\* \[→\]\(\S+\): I built this over a year\.\n\n### Genesis World")

    def test_ask_hn_uses_the_post_text(self):
        env, ex = self.run_main(str(ASK["id"]))
        ex.assert_not_called()
        content = Path(env["content_file"]).read_text()
        self.assertRegex(content, r"## Article\n\n\*\*\w+\*\* \[→\]\(https://news\.ycombinator\.com/item\?id=4102013\): ")
        self.assertIsNone(env["article_url"])

    def test_article_failure_keeps_the_discussion(self):
        env, _ = self.run_main(str(STORY), page=SkillError("no text could be extracted"))
        content = Path(env["content_file"]).read_text()
        self.assertIn("*The article could not be extracted: no text could be extracted*", content)
        self.assertEqual(env["comments"], 52)
        self.assertIn("article: failed", env["attempts"][0])

    def test_pdf_link_is_noted(self):
        env, _ = self.run_main(str(STORY), page=NotAPage("x is a application/pdf document"))
        self.assertIn("*The link is not a web page: x is a application/pdf document*",
                      Path(env["content_file"]).read_text())

    def test_no_article_flag(self):
        env, ex = self.run_main(str(STORY), "--no-article")
        ex.assert_not_called()
        self.assertIn("## Article\n\n*No article: a text post.*", Path(env["content_file"]).read_text())

    def test_other_source_is_refused(self):
        with self.assertRaisesRegex(SkillError, "is a web input"):
            prepare.main(["https://example.com/post"])


if __name__ == "__main__":
    unittest.main()

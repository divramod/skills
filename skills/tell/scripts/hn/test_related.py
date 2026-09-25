#!/usr/bin/env python3
"""Unit tests for hn/related.py (offline: a recorded Algolia search)."""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import related  # noqa: E402
from _common import SkillError  # noqa: E402

SEARCH = json.loads((HERE / "fixtures" / "past.search.json").read_text())
ARTICLE = "https://paulgraham.com/avg.html"


def with_other_url(hits: dict) -> dict:
    """The search also matches other pages of the site: those must be dropped."""
    extra = {"objectID": "999", "url": "http://www.paulgraham.com/avg.html/../hundred.html", "title": "Other",
             "num_comments": 500, "points": 900, "created_at": "2020-01-01T00:00:00Z"}
    return {"hits": hits["hits"] + [extra, {"objectID": "998", "url": None, "title": "Ask HN"}]}


class TestRelated(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def thread(self, name: str, id_: str, article: str | None, summary: bool = False) -> Path:
        folder = self.root / "discussions" / "hn" / name
        folder.mkdir(parents=True)
        (folder / "metadata.json").write_text(json.dumps(
            {"source": "hn", "id": id_, "extras": {"article_url": article} if article else {}}))
        if summary:
            (folder / "summary.html").write_text("<html></html>")
        return folder

    def test_same_article_other_threads_most_discussed_first(self):
        folder = self.thread("beating-the-averages-32053575", "32053575", ARTICLE)
        self.thread("beating-the-averages-1459836", "1459836", ARTICLE, summary=True)
        with mock.patch.object(related, "get_json", return_value=with_other_url(SEARCH)) as get:
            found = related.past_discussions(ARTICLE, "32053575", root=self.root, folder=folder)
        self.assertIn("restrictSearchableAttributes=url", get.call_args.args[0])
        ids = [d["id"] for d in found]
        self.assertNotIn("32053575", ids)  # the thread itself
        self.assertNotIn("999", ids)  # another page of the site
        self.assertEqual(len(ids), 10)  # the default limit
        self.assertEqual(ids[:2], ["1459836", "19022775"])  # 1 comment each, more points first
        self.assertEqual(found[0]["summary"], "../beating-the-averages-1459836/summary.html")
        self.assertEqual(found[0]["url"], "https://news.ycombinator.com/item?id=1459836")
        self.assertEqual(found[0]["date"], "2010-06-25")

    def test_same_page(self):
        self.assertTrue(related.same_page("http://www.paulgraham.com/avg.html", "https://paulgraham.com/avg.html"))
        self.assertTrue(related.same_page("https://a.dev/post/", "https://a.dev/post"))
        self.assertFalse(related.same_page("https://a.dev/post?id=1", "https://a.dev/post?id=2"))

    def test_text_post_has_nothing_to_search(self):
        folder = self.thread("ask-hn-1", "1", None)
        out = io.StringIO()
        with mock.patch.object(related, "get_json") as get, mock.patch.object(related, "log"), redirect_stdout(out):
            self.assertEqual(related.main([str(folder)]), 0)
        get.assert_not_called()
        self.assertEqual(json.loads(out.getvalue()), {"article": None, "discussions": []})

    def test_not_an_hn_folder(self):
        with self.assertRaisesRegex(SkillError, "not a prepared Hacker News thread"):
            related.main([self.tmp.name])


if __name__ == "__main__":
    unittest.main()

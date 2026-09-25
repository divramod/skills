#!/usr/bin/env python3
"""Unit tests for reddit/related.py (offline: a recorded Arctic Shift search)."""
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
ARTICLE = "https://theconsensus.dev/p/2026/09/06/data-races-and-the-limits-of-threadsanitizer-in-c-and-go.html"


def with_other_urls(found: dict) -> dict:
    """The search matches URL prefixes: other pages below the article must be dropped."""
    extra = {"id": "zzz", "url": ARTICLE + "/comments", "title": "Other", "subreddit": "x", "num_comments": 99,
             "score": 9, "created_utc": 1789000000}
    return {"data": found["data"] + [extra, {"id": "yyy", "url": None, "title": "no url"}]}


class TestRelated(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def post(self, name: str, id_: str, article: str | None, summary: bool = False) -> Path:
        folder = self.root / "discussions" / "reddit" / "sub" / name
        folder.mkdir(parents=True)
        (folder / "metadata.json").write_text(json.dumps(
            {"source": "reddit", "id": id_, "extras": {"article_url": article} if article else {}}))
        if summary:
            (folder / "summary.html").write_text("")
        return folder

    def test_other_posts_of_the_same_page_without_itself(self):
        own = self.post("own-1wexekt", "1wexekt", ARTICLE)
        self.post("other-1whiv8e", "1whiv8e", ARTICLE, summary=True)
        with mock.patch.object(related, "arctic", return_value=with_other_urls(SEARCH)):
            found = related.other_posts("http://www.theconsensus.dev/p/2026/09/06/data-races-and-the-limits-of-"
                                        "threadsanitizer-in-c-and-go.html/", "1wexekt", root=self.root, folder=own)
        self.assertEqual([f["id"] for f in found], ["1whiv8e"])
        self.assertEqual(found[0], {"id": "1whiv8e", "url": "https://www.reddit.com/r/hackernews/comments/1whiv8e/",
                                    "title": "Data races and the limits of ThreadSanitizer in C and Go",
                                    "subreddit": "hackernews", "score": 2, "comments": 1, "date": "2026-09-16",
                                    "summary": "../other-1whiv8e/summary.html"})

    def test_text_post_has_nothing_to_search(self):
        folder = self.post("q-1", "1", None)
        out = io.StringIO()
        with mock.patch.object(related, "arctic") as search, mock.patch.object(related, "log"), redirect_stdout(out):
            related.main([str(folder)])
        search.assert_not_called()
        self.assertEqual(json.loads(out.getvalue()), {"article": None, "discussions": []})

    def test_refuses_other_folders(self):
        with self.assertRaisesRegex(SkillError, "not a prepared Reddit post"):
            related.main([self.tmp.name])


if __name__ == "__main__":
    unittest.main()

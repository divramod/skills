#!/usr/bin/env python3
"""Unit tests for web/related.py (offline, temp library)."""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

import related
from _common import SkillError, write_json


class TestRelated(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.me = self.item("articles/site/me", "web", "https://site.com/me")
        self.other = self.item("articles/blog/other", "web", "https://blog.org/other", summary=True)
        self.item("articles/blog/draft", "web", "https://blog.org/draft")  # prepared, never summarized

    def item(self, rel, source, id_, summary=False) -> Path:
        folder = self.root / rel
        folder.mkdir(parents=True)
        write_json(folder / "metadata.json", {"source": source, "id": id_})
        if summary:
            (folder / "summary.html").write_text("<html></html>")
        return folder

    def test_drops_self_and_duplicates_marks_summaries(self):
        out = related.related(self.me, [
            "https://www.site.com/me?utm_source=x",  # the article itself
            "https://blog.org/other", "http://www.blog.org/other#x",  # summarized, then a duplicate
            "https://blog.org/draft", "https://new.dev/post",
        ], self.root)
        self.assertEqual([o["url"] for o in out], ["https://blog.org/other", "https://blog.org/draft",
                                                   "https://new.dev/post"])
        self.assertEqual(out[0]["summary"], "../../blog/other/summary.html")
        self.assertNotIn("summary", out[1])
        self.assertEqual(out[2]["source"], "web")

    def test_main_prints_json_and_checks_the_folder(self):
        buf = io.StringIO()
        with mock.patch.object(related, "library_root", return_value=self.root), redirect_stdout(buf):
            self.assertEqual(related.main([str(self.me), "--url", "https://github.com/astral-sh/uv"]), 0)
        self.assertEqual(json.loads(buf.getvalue())["articles"][0]["source"], "github")
        with self.assertRaisesRegex(SkillError, "not a prepared library folder"):
            related.main([str(self.root), "--url", "https://x.dev"])


if __name__ == "__main__":
    unittest.main()

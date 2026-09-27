#!/usr/bin/env python3
"""Unit tests for topic/search.py (offline: recorded Bing, Algolia, GitHub and yt-dlp answers for
"open knowledge format", and a temporary folder of local documents)."""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import search  # noqa: E402
from _common import SkillError  # noqa: E402

FIX = HERE / "fixtures"
Q = "open knowledge format"


def fixture(name: str):
    text = (FIX / name).read_text(encoding="utf-8")
    return json.loads(text) if name.endswith(".json") else text


class TestParsers(unittest.TestCase):
    def test_bing_results_go_to_the_source_that_reads_them(self):
        found = search.parse_bing(fixture("web.bing.rss"), Q)
        by = {c["input"]: c for c in found}
        repo = by["https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf"]
        self.assertEqual((repo["source"], repo["kind"]), ("github", "repo"))
        blog = by["https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-"
                  "data-sharing/"]
        self.assertEqual((blog["source"], blog["query"], blog["found"]), ("web", Q, "web search"))
        self.assertTrue(blog["snippet"])
        self.assertTrue(all("date" not in c for c in found))  # Bing's pubDate is its crawl date

    def test_bing_without_rss_is_an_error(self):
        with self.assertRaisesRegex(SkillError, "did not answer RSS"):
            search.parse_bing("<html>captcha", Q)

    def test_hn_stories(self):
        found = search.parse_hn(fixture("hn.algolia.json"), Q)
        first = found[0]
        self.assertEqual((first["source"], first["kind"]), ("hn", "item"))
        self.assertTrue(first["input"].startswith("https://news.ycombinator.com/item?id="))
        self.assertEqual(first["comments"], 15)
        self.assertRegex(first["date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertIn("article", first)

    def test_github_repos(self):
        found = search.parse_github(fixture("github.search.json"), Q)
        self.assertEqual(found[0]["input"], "https://github.com/GoogleCloudPlatform/open-knowledge-format")
        self.assertEqual((found[0]["source"], found[0]["kind"]), ("github", "repo"))
        self.assertIsInstance(found[0]["stars"], int)
        self.assertNotIn("fork", found[0])  # only set when true

    def test_videos_without_shorts_and_live(self):
        data = fixture("video.ytsearch.json")
        data["entries"] += [{"id": "live1234567", "title": "live", "live_status": "is_live"},
                            {"id": "short123456", "title": "s", "url": "https://www.youtube.com/shorts/short123456"}]
        found = search.parse_videos(data, Q)
        self.assertEqual(len(found), 6)
        self.assertEqual({c["source"] for c in found}, {"video"})
        self.assertTrue(all(c["input"].startswith("https://www.youtube.com/watch?v=") for c in found))
        self.assertRegex(found[0]["duration"], r"^\d+:\d{2}")

    def test_phrase(self):
        self.assertEqual(search.phrase("open knowledge format"), '"open knowledge format"')
        self.assertEqual(search.phrase("okf"), "okf")
        self.assertEqual(search.phrase('"a b" c'), '"a b" c')

    def test_candidate_drops_what_tell_cannot_read(self):
        self.assertIsNone(search.candidate("mailto:a@b.c", "x", Q))
        self.assertIsNone(search.candidate("", "x", Q))


class TestFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()

    def write(self, rel: str, text: str, age: int = 0) -> Path:
        p = self.home / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        t = time.time() - age
        os.utime(p, (t, t))
        return p

    def test_local_documents_names_first_then_newest(self):
        self.write("notes/meeting.md", "# Meeting\nwe talked about the Open Knowledge Format today\n", age=10)
        self.write("notes/older.txt", "open knowledge format, first look\n", age=1000)
        named = self.write("docs/open-knowledge-format.md", "spec notes\nOpen Knowledge Format v0.2\n", age=5000)
        self.write(".hidden/secret.md", "open knowledge format\n")
        self.write("node_modules/pkg/README.md", "open knowledge format\n")
        self.write("lib/topics/x/summary.md", "open knowledge format\n")  # the tell library itself
        self.write("data.json", '{"open knowledge format": 1}')  # not a document
        paths = [p for p in self.home.rglob("*") if p.is_file()]
        with mock.patch.object(search, "spotlight", return_value=paths), \
                mock.patch.object(search.sys, "platform", "darwin"), \
                mock.patch.object(search.shutil, "which", return_value="/usr/bin/mdfind"):
            found = search.files(Q, 10, [self.home], [self.home / "lib"])
        self.assertEqual([Path(c["input"]).name for c in found], ["open-knowledge-format.md", "meeting.md", "older.txt"])
        self.assertEqual(found[0]["input"], str(named))
        self.assertEqual((found[0]["source"], found[0]["kind"]), ("file", "md"))
        self.assertEqual(found[1]["snippet"], "we talked about the Open Knowledge Format today")
        self.assertRegex(found[1]["date"], r"^\d{4}-\d{2}-\d{2}$")

    def test_ripgrep_where_spotlight_is_missing(self):
        if not search.shutil.which("rg"):
            self.skipTest("rg not installed")
        self.write("a/notes.md", "About the OPEN knowledge format.\n")
        self.write("a/other.md", "nothing here\n")
        with mock.patch.object(search.sys, "platform", "linux"):
            found = search.files(Q, 5, [self.home])
        self.assertEqual([Path(c["input"]).name for c in found], ["notes.md"])

    def test_no_local_search_tool_is_a_missing_tool(self):
        from _common import MissingTool
        with mock.patch.object(search.sys, "platform", "linux"), \
                mock.patch.object(search.shutil, "which", return_value=None), \
                mock.patch("_common.shutil.which", return_value=None):
            with self.assertRaisesRegex(MissingTool, "rg"):
                search.files(Q, 5, [self.home])

    def test_default_dirs(self):
        with mock.patch.dict(os.environ, {"TELL_TOPIC_DIRS": f"{self.home}/a::~/b"}):
            self.assertEqual(search.default_dirs(), [self.home / "a", Path.home() / "b"])
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TELL_TOPIC_DIRS", None)
            self.assertEqual(search.default_dirs(), [Path.home()])


if __name__ == "__main__":
    unittest.main()

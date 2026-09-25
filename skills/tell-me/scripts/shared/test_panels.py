#!/usr/bin/env python3
"""Unit tests for panels.py (the header panels) and their use in render_html.py (offline)."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import panels
import render_html


def folder_with(meta: dict, files: dict | None = None) -> Path:
    tmp = Path(tempfile.mkdtemp())
    (tmp / "metadata.json").write_text(json.dumps(meta))
    for name, text in (files or {}).items():
        (tmp / name).write_text(text)
    return tmp


# Hermetic: HOME is an empty folder, so no test reads (or trips over) the real library under ~.
_home = tempfile.TemporaryDirectory()
_env = mock.patch.dict(os.environ, {"HOME": _home.name})


def setUpModule():
    _env.start()


def tearDownModule():
    _env.stop()
    _home.cleanup()


class TestPanels(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual([panels.num(n) for n in (0, 999, 9999, 28853, 1_000_000, 5_279_377)],
                         ["0", "999", "9,999", "28.9k", "1M", "5.3M"])

    def test_web(self):
        html = panels.web(Path("/nope"), {"site": "Simon Willison's Weblog", "word_count": 690,
                                          "extras": {"snapshot": "https://web.archive.org/x", "gone": True}}, None)
        self.assertIn("Simon Willison&#x27;s Weblog", html)
        self.assertIn("<b>3 min</b> read", html)
        self.assertIn('href="https://web.archive.org/x"', html)
        self.assertIn("the live page is gone", html)

    def test_github_repo_and_pull(self):
        repo = panels.github(Path("/"), {"extras": {
            "kind": "repo", "stars": 9503, "forks": 417, "license": "MIT", "languages": ["TypeScript 96%", "SCSS 4%"],
            "release": {"tag": "0.19.4", "date": "2026-09-17"}, "pushed_at": "2026-09-20", "archived": True}}, None)
        for want in ("<b>9,503</b> stars", "<b>417</b> forks", "MIT", "TypeScript 96%, SCSS 4%",
                     "release <b>0.19.4</b> (2026-09-17)", "last push 2026-09-20", "<b>archived</b>"):
            self.assertIn(want, repo)
        pull = panels.github(Path("/"), {"extras": {
            "kind": "pull", "number": 21966, "state": "closed", "merged": True, "comments": 4, "additions": 28,
            "deletions": 14, "changed_files": 1, "labels": ["internal"], "repo": "astral-sh/uv"}}, None)
        for want in ("pull <b>#21966</b>", "<b>merged</b>", "<b>4</b> comments", "<b>+28 −14</b> in 1 file",
                     "internal", 'href="https://github.com/astral-sh/uv"'):
            self.assertIn(want, pull)
        issue = panels.github(Path("/"), {"extras": {"kind": "issue", "number": 1, "state": "closed",
                                                     "state_reason": "not_planned"}}, None)
        self.assertIn("<b>closed (not planned)</b>", issue)

    def test_x(self):
        html = panels.x(Path("/"), {"extras": {"user": "karpathy", "views": 5279377, "likes": 28853, "reposts": 2269,
                                               "replies": 1754, "replies_fetched": 29, "posts": 2,
                                               "community_note": True}}, None)
        for want in ('href="https://x.com/karpathy"', "<b>5.3M</b> views", "<b>1,754</b> replies (29 read)",
                     "<b>2</b> posts in the thread", "community note"):
            self.assertIn(want, html)
        one = panels.x(Path("/"), {"extras": {"user": "a", "replies": 3, "replies_fetched": 3, "posts": 1}}, None)
        self.assertNotIn("read)", one)
        self.assertNotIn("posts in the thread", one)

    def test_hn(self):
        html = panels.hn(Path("/"), {"extras": {"points": 120, "comments": 45, "threads": 25,
                                                "article_url": "https://example.com/a"}}, None)
        for want in ("<b>120</b> points", "<b>45</b> comments in 25 threads", 'href="https://example.com/a"'):
            self.assertIn(want, html)
        self.assertIn("text post", panels.hn(Path("/"), {"extras": {"points": 3, "comments": 0}}, None))

    def test_file(self):
        folder = folder_with({}, {"original.pdf": "%PDF"})
        html = panels.file(folder, {"extras": {"kind": "pdf", "pages": 15, "size": 2_200_000,
                                               "original_file": "original.pdf", "versions": [{"sha256": "a"}]}},
                           None)
        for want in ("<b>PDF</b>", "<b>15</b> pages", "2.1 MB", 'href="original.pdf"', "version 2"):
            self.assertIn(want, html)
        gone = panels.file(Path("/nope"), {"extras": {"kind": "md", "size": 300, "original_file": "original.md"}},
                           None)
        self.assertNotIn("open the original", gone)
        self.assertIn("1 KB", gone)

    def test_nothing_to_show(self):
        self.assertEqual(panels.hn(Path("/"), {}, None), "")  # no points or comments: not known to be a text post
        self.assertEqual(panels.hn(Path("/"), {"extras": {"points": 5, "comments": 0}}, None),
                         '<ul class="facts"><li><b>5</b> points</li><li><b>0</b> comments</li><li>text post</li></ul>')
        self.assertEqual(panels.facts(None, ""), "")

    def test_only_http_links(self):
        for href in ("javascript:alert(1)", "JaVaScRiPt:alert(1)", "data:text/html,x", "//evil.example", None, 5):
            self.assertIsNone(panels.link(href, "x"), href)
        page = panels.hn(Path("/"), {"extras": {"points": 1, "article_url": "javascript:alert(1)"}}, None)
        self.assertNotIn("javascript", page)
        self.assertNotIn("text post", page)  # it has an article, just not one we link
        self.assertIn('href="https://a.example/?q=1&amp;b=2"', panels.link("https://a.example/?q=1&b=2", "a"))

    def test_the_original_is_a_file_in_the_folder(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "original.pdf").write_bytes(b"%PDF")
            self.assertIn('href="original.pdf"', panels.file(Path(d), {"extras": {"original_file": "original.pdf"}}, None))
            for name in ("../secret.pdf", "missing.pdf", "javascript:x", ["original.pdf"]):
                self.assertNotIn("<a", panels.file(Path(d), {"extras": {"original_file": name}}, None), name)

    def test_hostile_metadata_never_crashes(self):
        values = [None, "", "1,234", "many", [1, None], {"a": None}, True, -1, 3.7, "<script>"]
        fields = ("stars", "forks", "license", "languages", "release", "pushed_at", "labels", "state", "state_reason",
                  "number", "comments", "additions", "deletions", "changed_files", "repo", "kind", "user", "views",
                  "likes", "replies", "replies_fetched", "posts", "points", "threads", "article_url", "snapshot",
                  "size", "pages", "versions", "original_file", "language")
        for fn in panels.PANELS.values():
            for v in values:
                for meta in ({"extras": {f: v for f in fields}, "word_count": v, "site": v}, {"extras": v}):
                    out = fn(Path("/nonexistent"), meta, None)
                    self.assertNotIn("<script>", out)

    def test_numbers_given_as_strings(self):
        page = panels.github(Path("/"), {"extras": {"stars": "1,234", "forks": "many", "release": "v1.0",
                                                     "languages": {"Go": 10, "Rust": 90, "C": 1, "Zig": 5}}}, None)
        self.assertIn("<b>1,234</b> stars", page)
        self.assertNotIn("forks", page)
        self.assertNotIn("release", page)
        self.assertIn("Rust, Go, Zig", page)
        self.assertIn("in 2 threads", panels.hn(Path("/"), {"extras": {"comments": 3, "threads": 2}}, None))
        self.assertIn("in 1 thread<", panels.hn(Path("/"), {"extras": {"comments": 3, "threads": 1}}, None))


class TestRenderedPage(unittest.TestCase):
    def test_every_source_has_a_panel_and_an_x_video_gets_the_player(self):
        self.assertEqual(set(render_html.HEADER_PANELS), {"video", "web", "github", "x", "hn", "file"})
        meta = {"source": "x", "id": "1", "title": "A post", "url": "https://x.com/a/status/1", "video_file":
                "video.mp4", "video": {"source_url": "https://x.com/a/status/1", "playlist_item": 1},
                "extras": {"user": "a", "likes": 3}}
        folder = folder_with(meta, {"summary.md": "---\ntitle: A post\n---\n\n# A post\n\nbody\n",
                                    "content.md": "# A post\n\n## Thread\n", "video.mp4": ""})
        page = render_html.build(folder)
        self.assertIn('<ul class="facts">', page)
        self.assertIn("<video", page)
        self.assertIn(".facts{", page)

    def test_an_x_video_not_downloaded_gets_the_player_with_the_download_button(self):
        meta = {"source": "x", "id": "1", "title": "A post", "url": "https://x.com/a/status/1",
                "video": {"source_url": "https://x.com/a/status/1", "playlist_item": 2}, "extras": {"user": "a"}}
        page = render_html.build(folder_with(meta, {"summary.md": "# A post\n\nbody\n", "content.md": "# A\n"}))
        self.assertIn('<div class="dl" hidden>', page)
        self.assertIn(".dl[hidden]{display:none}", page)

    def test_an_x_post_without_a_video_part_has_no_player(self):
        meta = {"source": "x", "id": "1", "title": "A post", "url": "https://x.com/a/status/1", "extras": {"user": "a"}}
        page = render_html.build(folder_with(meta, {"summary.md": "# A post\n\nbody\n", "content.md": "# A\n"}))
        self.assertNotIn('class="player"', page)

    def test_a_failing_panel_renders_the_page_without_it(self):
        meta = {"source": "web", "id": "1", "title": "A page", "url": "https://a.example/"}
        folder = folder_with(meta, {"summary.md": "# A page\n\nbody\n", "content.md": "# A\n"})
        with mock.patch.dict(render_html.HEADER_PANELS, {"web": mock.Mock(side_effect=KeyError("boom"))}):
            page = render_html.build(folder)
        self.assertIn("<p>body</p>", page)
        self.assertNotIn('class="facts"', page)


if __name__ == "__main__":
    unittest.main()

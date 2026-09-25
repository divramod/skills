#!/usr/bin/env python3
"""Unit tests for panels.py (the header panels) and their use in render_html.py (offline)."""
import json
import tempfile
import unittest
from pathlib import Path

import panels
import render_html


def folder_with(meta: dict, files: dict | None = None) -> Path:
    tmp = Path(tempfile.mkdtemp())
    (tmp / "metadata.json").write_text(json.dumps(meta))
    for name, text in (files or {}).items():
        (tmp / name).write_text(text)
    return tmp


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
        for want in ("pull <b>#21966</b>", "<b>merged</b>", "<b>4</b> comments", "<b>+28 −14</b> in 1 files",
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
        self.assertEqual(panels.hn(Path("/"), {}, None), '<ul class="facts"><li>text post</li></ul>')
        self.assertEqual(panels.facts(None, ""), "")


class TestRenderedPage(unittest.TestCase):
    def test_every_source_has_a_panel_and_an_x_video_gets_the_player(self):
        self.assertEqual(set(render_html.HEADER_PANELS), {"video", "web", "github", "x", "hn", "file"})
        meta = {"source": "x", "id": "1", "title": "A post", "url": "https://x.com/a/status/1", "video_file":
                "video.mp4", "extras": {"user": "a", "likes": 3}}
        folder = folder_with(meta, {"summary.md": "---\ntitle: A post\n---\n\n# A post\n\nbody\n",
                                    "content.md": "# A post\n\n## Thread\n", "video.mp4": ""})
        page = render_html.build(folder)
        self.assertIn('<ul class="facts">', page)
        self.assertIn("<video", page)
        self.assertIn(".facts{", page)


if __name__ == "__main__":
    unittest.main()

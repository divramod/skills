#!/usr/bin/env python3
"""Unit tests for save_summary.py (offline)."""
import json
import tempfile
import unittest
from pathlib import Path

from save_summary import fmt_date, refresh, render, set_frontmatter_field, strip_leading_h1

META = {"id": "abc", "title": 'Say "hi": a test', "channel": "Chan", "webpage_url": "https://www.youtube.com/watch?v=abc",
        "upload_date": "20260924", "duration": 729, "platform": "youtube", "transcript_source": "captions (manual, en)"}


class TestSaveSummary(unittest.TestCase):
    def test_other_source_frontmatter(self):
        md = render({"source": "hn", "id": "1", "title": "Y", "author": "pg", "url": "https://news.ycombinator.com/item?id=1",
                     "published": "2007-02-19", "site": "Hacker News", "extractor": "algolia"}, "x", "summary", "en", "2026-09-25")
        self.assertIn('source: "hn"\nauthor: "pg"\nurl: "https://news.ycombinator.com/item?id=1"\npublished: "2007-02-19"'
                      '\nsite: "Hacker News"\nid: "1"', md)
        self.assertIn("# Y\n\npg · 2007-02-19 · https://news.ycombinator.com/item?id=1\n", md)

    def test_frontmatter_and_header(self):
        md = render(META, "**TL;DR:** ok", "wisdom", "de", "2026-09-25")
        self.assertTrue(md.startswith("---\n"))
        self.assertIn('title: "Say \\"hi\\": a test"', md)
        self.assertIn('published: "2026-09-24"', md)
        self.assertIn('duration: "12:09"', md)
        self.assertIn('id: "abc"', md)
        self.assertIn('source: "video"\nauthor: "Chan"', md)
        self.assertIn('extractor: "captions (manual, en)"', md)
        self.assertIn('mode: "wisdom"', md)
        self.assertIn('lang: "de"', md)
        self.assertIn('created: "2026-09-25"', md)
        self.assertIn('# Say "hi": a test\n\nChan · 12:09 · 2026-09-24 · https://www.youtube.com/watch?v=abc\n\n**TL;DR:** ok', md)

    def test_agent_h1_is_not_duplicated(self):
        self.assertEqual(strip_leading_h1("# Title\n\nbody"), "body")
        self.assertEqual(strip_leading_h1("body\n# later"), "body\n# later")

    def test_digest_frontmatter(self):
        md = render({"kind": "digest", "title": "PL", "videos": [{}, {}]}, "x", "digest", None, "2026-09-25")
        self.assertIn("items: 2", md)
        self.assertNotIn("id:", md)
        self.assertNotIn("lang:", md)

    def test_agent_and_model_in_frontmatter(self):
        md = render(META, "x", "summary", "en", "2026-09-25", "codex", "gpt-x")
        self.assertIn('agent: "codex"\nmodel: "gpt-x"\ncreated: "2026-09-25"', md)
        self.assertNotIn("model:", render(META, "x", "summary", "en", "2026-09-25", "grok"))

    def test_set_frontmatter_field(self):
        md = render(META, "x", "summary", "en", "2026-09-25", "codex")
        added = set_frontmatter_field(md, "video_file", "video.mkv")
        self.assertIn('video_file: "video.mkv"\nagent: "codex"', added)
        self.assertIn('video_file: "video.mp4"', set_frontmatter_field(added, "video_file", "video.mp4"))
        self.assertEqual(added.count("video_file"), 1)
        self.assertEqual(set_frontmatter_field("no frontmatter", "k", "v"), "no frontmatter")

    def test_refresh_after_background_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.assertEqual(refresh(folder), [])
            (folder / "metadata.json").write_text(json.dumps(META))
            (folder / "summary.md").write_text(render(META, "x", "summary", "en", "2026-09-25"))
            (folder / "metadata.json").write_text(json.dumps(META | {"video_file": "video.mkv"}))
            (folder / "video.mkv").write_bytes(b"")
            written = refresh(folder)
            self.assertEqual([p.name for p in written], ["summary.md", "summary.html"])
            self.assertIn('video_file: "video.mkv"', (folder / "summary.md").read_text())
            self.assertIn("<video", (folder / "summary.html").read_text())
            (folder / "video.mkv").unlink()  # deleted again
            (folder / "metadata.json").write_text(json.dumps(META))
            refresh(folder)
            self.assertNotIn("video_file", (folder / "summary.md").read_text())
            self.assertNotIn("<video", (folder / "summary.html").read_text())

    def test_fmt_date(self):
        self.assertEqual(fmt_date("20260924"), "2026-09-24")
        self.assertIsNone(fmt_date(None))


if __name__ == "__main__":
    unittest.main()

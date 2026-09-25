#!/usr/bin/env python3
"""Unit tests for save_summary.py (offline)."""
import unittest

from save_summary import fmt_date, render, strip_leading_h1

META = {"id": "abc", "title": 'Say "hi": a test', "channel": "Chan", "webpage_url": "https://www.youtube.com/watch?v=abc",
        "upload_date": "20260924", "duration": 729, "platform": "youtube", "transcript_source": "captions (manual, en)"}


class TestSaveSummary(unittest.TestCase):
    def test_frontmatter_and_header(self):
        md = render(META, "**TL;DR:** ok", "wisdom", "de", "2026-09-25")
        self.assertTrue(md.startswith("---\n"))
        self.assertIn('title: "Say \\"hi\\": a test"', md)
        self.assertIn('published: "2026-09-24"', md)
        self.assertIn('duration: "12:09"', md)
        self.assertIn('video_id: "abc"', md)
        self.assertIn('mode: "wisdom"', md)
        self.assertIn('lang: "de"', md)
        self.assertIn('created: "2026-09-25"', md)
        self.assertIn('# Say "hi": a test\n\nChan · 12:09 · 2026-09-24 · https://www.youtube.com/watch?v=abc\n\n**TL;DR:** ok', md)

    def test_agent_h1_is_not_duplicated(self):
        self.assertEqual(strip_leading_h1("# Title\n\nbody"), "body")
        self.assertEqual(strip_leading_h1("body\n# later"), "body\n# later")

    def test_digest_frontmatter(self):
        md = render({"kind": "digest", "title": "PL", "videos": [{}, {}]}, "x", "digest", None, "2026-09-25")
        self.assertIn("videos: 2", md)
        self.assertNotIn("video_id", md)
        self.assertNotIn("lang:", md)

    def test_fmt_date(self):
        self.assertEqual(fmt_date("20260924"), "2026-09-24")
        self.assertIsNone(fmt_date(None))


if __name__ == "__main__":
    unittest.main()

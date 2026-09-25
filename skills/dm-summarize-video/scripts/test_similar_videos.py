#!/usr/bin/env python3
"""Unit tests for similar_videos.py (offline)."""
import unittest
from pathlib import Path

from similar_videos import merge


class TestMerge(unittest.TestCase):
    def test_dedupes_excludes_self_marks_summarized(self):
        results = [
            ("q1", [{"id": "self", "title": "Me"}, {"id": "a", "title": "A", "channel": "C", "duration": 125, "view_count": 9},
                    {"id": "live", "title": "L", "live_status": "is_live"},
                    {"id": "s", "title": "Short", "url": "https://www.youtube.com/shorts/s"}]),
            ("q2", [{"id": "a", "title": "A again"}, {"id": "b", "title": "B"}]),
        ]
        known = {"b": Path("/lib/youtube/x/b/summary.html")}
        videos = merge(results, "self", known, Path("/lib/youtube/me/video"))
        self.assertEqual(videos, [
            {"id": "a", "title": "A", "url": "https://www.youtube.com/watch?v=a", "channel": "C", "duration": "02:05",
             "views": 9, "query": "q1"},
            {"id": "b", "title": "B", "url": "https://www.youtube.com/watch?v=b", "query": "q2",
             "summary": "../../x/b/summary.html"},
        ])


if __name__ == "__main__":
    unittest.main()

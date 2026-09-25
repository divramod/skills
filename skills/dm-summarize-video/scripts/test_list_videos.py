#!/usr/bin/env python3
"""Unit tests for list_videos.py (offline)."""
import unittest

from _common import SkillError
from list_videos import normalize_url, parse_listing

PLAYLIST = {
    "extractor_key": "YoutubeTab", "title": "My Playlist", "channel": "Chan",
    "entries": [
        {"_type": "url", "id": "a1", "title": "One", "url": "https://www.youtube.com/watch?v=a1", "duration": 60},
        {"_type": "url", "id": "b2", "title": "Two", "url": "https://youtube.com/shorts/b2", "duration": 30},
        None,
    ],
}


class TestListVideos(unittest.TestCase):
    def test_normalize_channel_urls(self):
        self.assertEqual(normalize_url("https://www.youtube.com/@chan"), ("https://www.youtube.com/@chan/videos", "channel"))
        self.assertEqual(normalize_url("https://www.youtube.com/channel/UC1/"), ("https://www.youtube.com/channel/UC1/videos", "channel"))
        self.assertEqual(normalize_url("https://www.youtube.com/@chan/videos"), ("https://www.youtube.com/@chan/videos", "channel"))
        self.assertEqual(normalize_url("https://www.youtube.com/playlist?list=PL1")[1], "playlist")

    def test_parse_playlist(self):
        out = parse_listing(PLAYLIST, "playlist", None, "2026-09-25")
        self.assertEqual(out["slug"], "my-playlist")
        self.assertEqual([v["url"] for v in out["videos"]],
                         ["https://www.youtube.com/watch?v=a1", "https://www.youtube.com/watch?v=b2"])

    def test_parse_channel_limit_and_slug(self):
        out = parse_listing(PLAYLIST, "channel", 1, "2026-09-25")
        self.assertEqual(len(out["videos"]), 1)
        self.assertEqual(out["slug"], "chan-latest-1-2026-09-25")

    def test_tabs_rejected(self):
        with self.assertRaises(SkillError):
            parse_listing({"entries": [{"_type": "playlist"}]}, "channel", None, "2026-09-25")


if __name__ == "__main__":
    unittest.main()

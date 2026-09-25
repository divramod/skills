#!/usr/bin/env python3
"""Unit tests for _common.py (offline)."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _common import (MissingTool, find_existing, library_root, platform_of, require, slugify, ts_link,
                     ts_url, user_of, video_dir)


class TestNaming(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(slugify("Jev Explained in 12 mins (Without the Hype)"), "jev-explained-in-12-mins-without-the-hype")
        self.assertEqual(slugify("Über Größe: ä/ö"), "uber-groe-a-o")
        self.assertEqual(slugify(""), "untitled")
        self.assertEqual(slugify("a" * 100, max_len=10), "a" * 10)

    def test_platform(self):
        self.assertEqual(platform_of({"extractor_key": "Youtube"}), "youtube")
        self.assertEqual(platform_of({"extractor_key": "YoutubeTab"}), "youtube")
        self.assertEqual(platform_of({"extractor_key": "TikTok"}), "tiktok")
        self.assertEqual(platform_of({}), "video")

    def test_user_prefers_handle_without_at(self):
        self.assertEqual(user_of({"uploader_id": "@AishReganti", "channel": "Aish Reganti"}), "aishreganti")
        self.assertEqual(user_of({"channel": "Aish Reganti"}), "aish-reganti")
        self.assertEqual(user_of({}), "unknown")

    def test_video_dir_layout(self):
        info = {"extractor_key": "Youtube", "uploader_id": "@chan", "title": "My Video!"}
        self.assertEqual(video_dir(info, Path("/r")), Path("/r/youtube/chan/my-video"))

    def test_default_root_and_env_override(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(library_root(), Path.home() / "me" / "summaries" / "videos")
        with mock.patch.dict(os.environ, {"DM_SUMMARIZE_VIDEO_ROOT": "/tmp/x"}):
            self.assertEqual(library_root(), Path("/tmp/x"))


class TestFindExisting(unittest.TestCase):
    def test_finds_by_id_even_after_title_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "youtube" / "chan" / "old-title"
            old.mkdir(parents=True)
            (old / "metadata.json").write_text(json.dumps({"id": "abc"}))
            info = {"extractor_key": "Youtube", "id": "abc", "title": "New Title"}
            self.assertEqual(find_existing(info, root), old)
            self.assertIsNone(find_existing({**info, "id": "zzz"}, root))
            self.assertIsNone(find_existing({**info, "extractor_key": "Vimeo"}, root))


class TestLinks(unittest.TestCase):
    def test_youtube_canonical_link_for_any_input_url(self):
        info = {"extractor_key": "Youtube", "id": "abc", "webpage_url": "https://youtu.be/abc"}
        self.assertEqual(ts_url(info, 61.9), "https://www.youtube.com/watch?v=abc&t=61s")
        self.assertEqual(ts_link(info, 61), "[01:01](https://www.youtube.com/watch?v=abc&t=61s)")

    def test_vimeo_and_unknown(self):
        self.assertEqual(ts_url({"extractor_key": "Vimeo", "webpage_url": "https://vimeo.com/1"}, 5), "https://vimeo.com/1#t=5s")
        self.assertEqual(ts_link({"extractor_key": "Generic"}, 5), "00:05")


class TestRequire(unittest.TestCase):
    def test_missing_tool_message(self):
        with self.assertRaises(MissingTool) as cm:
            require("python3", "definitely-not-a-tool-xyz")
        self.assertIn("definitely-not-a-tool-xyz", str(cm.exception))
        self.assertIn("install-prerequisites.sh", str(cm.exception))
        require("python3")  # present: no error


if __name__ == "__main__":
    unittest.main()

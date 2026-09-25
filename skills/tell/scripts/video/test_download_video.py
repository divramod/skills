#!/usr/bin/env python3
"""Unit tests for download_video.py (offline)."""
import json
import os
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

from download_video import (DOWNLOAD_FORMATS, STATUS_FILE, delete_video, download_action, download_status, ffmetadata,
                            is_running, parse_progress, record)
from _common import SkillError


class TestDownloadAction(unittest.TestCase):
    def test_decisions(self):
        self.assertEqual(download_action(False, "best", None), "download")
        self.assertEqual(download_action(True, "best", "best"), "reuse")
        self.assertEqual(download_action(True, "best", "1080p"), "replace")
        self.assertEqual(download_action(True, "best", None), "replace")  # pre-quality-tracking file
        self.assertEqual(download_action(True, "1080p", "best"), "reuse")
        self.assertEqual(download_action(True, "1080p", "1080p"), "reuse")

    def test_best_format_has_no_height_cap(self):
        self.assertNotIn("height", DOWNLOAD_FORMATS["best"])
        self.assertIn("height<=1080", DOWNLOAD_FORMATS["1080p"])


class TestProgress(unittest.TestCase):
    def test_parse_progress(self):
        self.assertEqual(parse_progress("[download]  42.3% of  120.00MiB at  5.00MiB/s ETA 00:12"), 42.3)
        self.assertEqual(parse_progress("[download] 100% of   10.00MiB in 00:00:02"), 100.0)
        self.assertIsNone(parse_progress("[download] Destination: video.f137.mp4"))
        self.assertIsNone(parse_progress("[Merger] Merging formats"))


class TestFfmetadata(unittest.TestCase):
    def test_tags_escaping_and_chapters(self):
        text = ffmetadata({"title": "A = b; #1", "channel": "Chan", "upload_date": "20260924",
                           "webpage_url": "https://y.com/?v=1", "duration": 70,
                           "chapters": [{"start_time": 42, "title": "Main"}, {"start_time": 0, "title": "Intro"}]})
        self.assertEqual(text.splitlines()[:5], [";FFMETADATA1", "title=A \\= b\\; \\#1", "artist=Chan", "date=2026",
                                                 "comment=https://y.com/?v\\=1"])
        self.assertIn("[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=42000\ntitle=Intro", text)
        self.assertIn("START=42000\nEND=70000\ntitle=Main", text)

    def test_last_chapter_without_duration_is_dropped(self):
        text = ffmetadata({"title": "T", "chapters": [{"start_time": 0, "title": "A"}, {"start_time": 5, "title": "B"}]})
        self.assertEqual(text.count("[CHAPTER]"), 1)


class TestStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_status_file(self):
        self.assertIsNone(download_status(self.dir))
        self.assertFalse(is_running(self.dir))

    def test_running_with_live_pid(self):
        (self.dir / STATUS_FILE).write_text(json.dumps({"status": "running", "pid": os.getpid()}))
        self.assertTrue(is_running(self.dir))

    def test_dead_pid_reports_failed(self):
        (self.dir / STATUS_FILE).write_text(json.dumps({"status": "running", "pid": 2 ** 22 + 12345}))
        self.assertEqual(download_status(self.dir)["status"], "failed")
        self.assertFalse(is_running(self.dir))

    def test_delete_video(self):
        (self.dir / "video.mkv").write_bytes(b"x")
        (self.dir / "metadata.json").write_text(json.dumps({"id": "a", "video_file": "video.mkv", "video_quality": "best"}))
        self.assertEqual(delete_video(self.dir), self.dir / "video.mkv")
        self.assertFalse((self.dir / "video.mkv").exists())
        self.assertEqual(json.loads((self.dir / "metadata.json").read_text()), {"id": "a"})
        self.assertIsNone(delete_video(self.dir))  # idempotent

    def test_delete_refuses_while_downloading(self):
        (self.dir / STATUS_FILE).write_text(json.dumps({"status": "running", "pid": os.getpid()}))
        with self.assertRaises(SkillError):
            delete_video(self.dir)

    def test_record_merges_into_metadata(self):
        (self.dir / "metadata.json").write_text(json.dumps({"id": "abc", "transcript_source": "x"}))
        record(self.dir, self.dir / "video.mkv", "best")
        meta = json.loads((self.dir / "metadata.json").read_text())
        self.assertEqual(meta, {"id": "abc", "transcript_source": "x", "video_file": "video.mkv", "video_quality": "best"})

    def test_refresh_never_migrates_another_sources_folder(self):
        from unittest import mock
        import download_video
        (self.dir / "metadata.json").write_text(json.dumps({"source": "x", "title": "A post", "video": {}}))
        with mock.patch("migrate_library.migrate_folder") as migrate, \
                mock.patch("save_summary.refresh", return_value=[]):
            download_video.refresh(self.dir)
        migrate.assert_not_called()
        self.assertEqual(json.loads((self.dir / "metadata.json").read_text())["source"], "x")

    def test_one_video_of_several_is_passed_on(self):
        from unittest import mock
        import download_video
        with mock.patch.object(download_video.subprocess, "Popen") as popen:
            popen.return_value.pid = 1
            download_video.start_background(self.dir, "https://x.com/p/status/1", "best", None, None, 2)
        self.assertEqual(popen.call_args.args[0][-2:], ["--playlist-item", "2"])
        (self.dir / STATUS_FILE).unlink()
        with mock.patch.object(download_video.subprocess, "Popen") as popen:
            popen.return_value.stdout = []
            with self.assertRaises(SkillError):  # no file appears: the fake yt-dlp downloads nothing
                download_video.download(self.dir, "https://x.com/p/status/1", "best", None, None, item=2)
        cmd = popen.call_args.args[0]
        self.assertEqual(cmd[cmd.index("--playlist-items") + 1], "2")


if __name__ == "__main__":
    unittest.main()

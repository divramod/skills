#!/usr/bin/env python3
"""Unit tests for migrate_library.py on a temp library (offline)."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

from migrate_library import migrate
from save_summary import render

OLD_META = {"id": "abc", "title": "Talk", "channel": "Chan", "webpage_url": "https://www.youtube.com/watch?v=abc",
            "upload_date": "20260924", "duration": 61, "platform": "youtube", "transcript_source": "captions",
            "prepared_at": "2026-09-24T10:00:00", "view_count": 7, "chapters": [{"start_time": 0, "title": "a"}]}


class TestMigrate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.env = mock.patch.dict(os.environ, {"TELL_ME_ROOT": str(self.root)})
        self.env.start()
        self.folder = self.root / "videos" / "youtube" / "chan" / "talk"
        self.folder.mkdir(parents=True)
        (self.folder / "metadata.json").write_text(json.dumps(OLD_META))
        (self.folder / "transcript.md").write_text("# Talk\n\none two three")
        (self.folder / "summary.md").write_text(render(OLD_META, "**TL;DR:** ok", "tldr", "en", "2026-09-25"))
        (self.folder / "summary.html").write_text('<script src="../../../library.js"></script>')
        (self.root / "videos" / "library.js").write_text("window.DM_LIBRARY = {};")

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_dry_run_changes_nothing(self):
        result = migrate(self.root, apply=False)
        self.assertEqual(len(result["folders"]), 1)
        self.assertIn("rename transcript.md -> content.md", result["folders"][0]["actions"])
        self.assertTrue((self.folder / "transcript.md").exists())
        self.assertTrue((self.root / "videos" / "library.js").exists())
        self.assertNotIn("source", json.loads((self.folder / "metadata.json").read_text()))

    def test_apply_then_second_run_is_a_no_op(self):
        result = migrate(self.root, apply=True)
        self.assertEqual(result["folders"][0]["actions"], [
            "rename transcript.md -> content.md",
            "add contract fields: source, url, author, published, fetched, site, word_count, extractor, content_file, extras",
            "re-render page"])
        self.assertFalse((self.folder / "transcript.md").exists())
        self.assertEqual((self.folder / "content.md").read_text(), "# Talk\n\none two three")
        meta = json.loads((self.folder / "metadata.json").read_text())
        self.assertEqual({k: meta[k] for k in ("source", "author", "published", "site", "word_count", "content_file",
                                               "extras")},
                         {"source": "video", "author": "Chan", "published": "2026-09-24", "site": "youtube",
                          "word_count": 5, "content_file": "content.md", "extras": {"views": 7, "chapters": 1}})
        self.assertEqual(meta["channel"], "Chan")  # yt-dlp keys stay
        page = (self.folder / "summary.html").read_text()
        self.assertIn('<script src="../../../../library.js"></script>', page)
        self.assertIn('<details class="content"><summary>Transcript</summary>', page)
        self.assertFalse((self.root / "videos" / "library.js").exists())
        self.assertTrue((self.root / "library.js").exists())
        again = migrate(self.root, apply=True)
        self.assertEqual((again["folders"], again["removed"]), ([], None))

    def test_only_stops_a_server_serving_this_folder(self):
        import subprocess
        from migrate_library import stop_old_server
        videos = self.root / "videos"
        other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            (videos / ".server.json").write_text(json.dumps({"pid": other.pid, "port": 1}))
            self.assertIsNone(stop_old_server(videos))
            self.assertIsNone(other.poll())  # still running
            self.assertFalse((videos / ".server.json").exists())
        finally:
            other.kill()
            other.wait()

    def test_unreadable_metadata_and_running_downloads_are_skipped(self):
        broken = self.root / "videos" / "youtube" / "chan" / "broken"
        broken.mkdir(parents=True)
        (broken / "metadata.json").write_text('{"id": "x", "tit')
        (broken / "transcript.md").write_text("t")
        (self.folder / ".video-download.json").write_text(json.dumps({"status": "running", "pid": 1}))
        result = migrate(self.root, apply=True)
        self.assertEqual(result["folders"], [])
        self.assertEqual(sorted(Path(s["dir"]).name for s in result["skipped"]), ["broken", "talk"])
        self.assertEqual((broken / "metadata.json").read_text(), '{"id": "x", "tit')
        self.assertTrue((broken / "transcript.md").exists() and (self.folder / "transcript.md").exists())

    def test_migrate_one_folder(self):
        from migrate_library import migrate_folder
        self.assertEqual(migrate_folder(self.folder)["actions"][0], "rename transcript.md -> content.md")
        self.assertTrue((self.folder / "content.md").exists())
        self.assertIsNone(migrate_folder(self.folder))

    def test_another_sources_folder_is_left_alone(self):
        from migrate_library import migrate_folder
        post = self.root / "posts" / "x" / "u" / "p-1"
        post.mkdir(parents=True)
        meta = {"source": "x", "id": "1", "title": "A post", "video": {"transcript_file": "video-transcript.md"}}
        (post / "metadata.json").write_text(json.dumps(meta))
        self.assertIsNone(migrate_folder(post))
        self.assertEqual(json.loads((post / "metadata.json").read_text()), meta)

    def test_empty_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(migrate(Path(tmp), apply=True)["folders"], [])


if __name__ == "__main__":
    unittest.main()

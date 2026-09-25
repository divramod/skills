#!/usr/bin/env python3
"""Unit tests for _common.py (offline)."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _common import (MissingTool, SkillError, browser_cookies, detect_agent, install_script, dir_for, find_by_id, source_root, unique_dir, find_existing, find_file, library_root, platform_of, require, slugify, ts_link,
                     ts_url, update_json, user_of, video_dir)


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
            self.assertEqual(library_root(), Path.home() / "me" / "summaries")
            self.assertEqual(source_root("video"), Path.home() / "me" / "summaries" / "videos")
        with mock.patch.dict(os.environ, {"TELL_ME_ROOT": "/tmp/x", "DM_SUMMARIZE_VIDEO_ROOT": "/tmp/y/videos"}):
            self.assertEqual(library_root(), Path("/tmp/x"))
        with mock.patch.dict(os.environ, {"DM_SUMMARIZE_VIDEO_ROOT": "/tmp/y/videos"}, clear=True):
            self.assertEqual(library_root(), Path("/tmp/y"))  # the old variable pointed at the videos subtree
        with mock.patch.dict(os.environ, {"DM_SUMMARIZE_VIDEO_ROOT": "/tmp/yt-notes"}, clear=True):
            with self.assertRaisesRegex(SkillError, "set TELL_ME_ROOT"):
                library_root()  # its parent may be ~: never guess

    def test_browser_cookies_new_name_first_then_the_old_one(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(browser_cookies())
        with mock.patch.dict(os.environ, {"DM_SUMMARIZE_VIDEO_BROWSER": "firefox"}, clear=True):
            self.assertEqual(browser_cookies(), "firefox")
        with mock.patch.dict(os.environ, {"TELL_ME_BROWSER": "chrome", "DM_SUMMARIZE_VIDEO_BROWSER": "firefox"}):
            self.assertEqual(browser_cookies(), "chrome")

    def test_unique_dir_on_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta = {"source": "web", "site": "s", "title": "Home", "id": "https://s/a"}
            first = unique_dir(meta, Path(tmp))
            first.mkdir(parents=True)
            (first / "metadata.json").write_text(json.dumps(meta))
            self.assertEqual(unique_dir(meta, Path(tmp)), first)  # same item: same folder
            other = unique_dir(meta | {"id": "https://s/b"}, Path(tmp))
            self.assertEqual(other.parent, first.parent)
            self.assertRegex(other.name, r"^home-[0-9a-f]{6}$")

    def test_dir_for_each_source(self):
        r = Path("/r")
        cases = [
            ({"extractor_key": "Youtube", "uploader_id": "@chan", "title": "My Video!"}, "videos/youtube/chan/my-video"),
            ({"source": "video", "platform": "youtube", "extractor_key": "Youtube", "uploader_id": "@c", "title": "T"},
             "videos/youtube/c/t"),
            ({"source": "web", "site": "Simon Willison", "url": "https://simonwillison.net/x", "title": "A Post"},
             "articles/simon-willison/a-post"),
            ({"source": "web", "url": "https://www.example.com/x", "title": "A Post"}, "articles/example-com/a-post"),
            ({"source": "github", "id": "yt-dlp/yt-dlp", "title": "yt-dlp"}, "repos/github/yt-dlp/yt-dlp"),
            ({"source": "github", "id": "o/r#12", "title": "Crash on start", "extras": {"kind": "pull"}},
             "repos/github/o/r/pulls/12-crash-on-start"),
            ({"source": "x", "id": "20", "author": "Jack", "title": "just setting up my twttr", "extras": {"user": "jack"}},
             "posts/x/jack/just-setting-up-my-twttr-20"),
            ({"source": "hn", "id": "1", "title": "Y Combinator"}, "discussions/hn/y-combinator-1"),
            ({"source": "file", "url": "file:///Users/a/Papers/Attention Is All You Need.pdf", "title": "x"},
             "documents/papers/attention-is-all-you-need"),
        ]
        for meta, rel in cases:
            with self.subTest(rel):
                self.assertEqual(dir_for(meta, r), r / rel)


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


class TestFindById(unittest.TestCase):
    def test_finds_any_source_by_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            post = root / "articles" / "site" / "old-title"
            post.mkdir(parents=True)
            (post / "metadata.json").write_text(json.dumps({"source": "web", "id": "https://a.b/p",
                                                            "extras": {"aliases": ["https://t.co/x"]}}))
            self.assertEqual(find_by_id("web", "https://a.b/p", root), post)
            self.assertEqual(find_by_id("web", "https://t.co/x", root), post)  # an alias (short link)
            self.assertIsNone(find_by_id("web", "https://a.b/q", root))
            self.assertIsNone(find_by_id("hn", "https://a.b/p", root))
            self.assertIsNone(find_by_id("web", None, root))


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

    def test_install_script_of_the_running_source(self):
        scripts = Path(__file__).resolve().parent.parent
        self.assertEqual(install_script(str(scripts / "video" / "prepare.py")), scripts / "video" / "install-prerequisites.sh")
        self.assertEqual(install_script(str(scripts / "hn" / "prepare.py")), scripts / "hn" / "install-prerequisites.sh")
        self.assertEqual(install_script("/elsewhere/run.py"), scripts / "install-prerequisites.sh")


class TestAgentAndFiles(unittest.TestCase):
    def test_detect_agent(self):
        self.assertEqual(detect_agent({"AI_AGENT": "claude-code_2-1-282_agent", "CODEX_SANDBOX": "1"}), "claude-code 2.1.282")
        self.assertEqual(detect_agent({"AI_AGENT": "grok"}), "grok")
        self.assertEqual(detect_agent({"CLAUDECODE": "1"}), "claude-code")
        self.assertEqual(detect_agent({"CODEX_THREAD_ID": "t"}), "codex")
        self.assertEqual(detect_agent({"GROK_CLI": "1"}), "grok")
        self.assertIsNone(detect_agent({}))

    def test_find_file_skips_ytdlp_work_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for name in ("video.f137.mp4", "video.f140.m4a.part", "video.temp.mkv", "video.mkv.part", "video.mkv.ytdl"):
                (d / name).write_bytes(b"")
            self.assertIsNone(find_file(d, "video"))
            (d / "video.mkv").write_bytes(b"")
            self.assertEqual(find_file(d, "video"), d / "video.mkv")

    def test_update_json_merges_and_drops(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metadata.json"
            path.write_text(json.dumps({"a": 1, "video": {"x": 1}, "keep": True}))
            self.assertEqual(update_json(path, {"a": 2}, drop=("video", "absent")), {"a": 2, "keep": True})
            self.assertEqual(json.loads(path.read_text()), {"a": 2, "keep": True})


class TestDigestDir(unittest.TestCase):
    def test_folder_metadata_reuse_and_collision(self):
        import json
        import tempfile
        from _common import digest_dir
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            items = [{"title": "Alpha Post", "dir": "/a"}, {"title": "Beta", "dir": "/b"}]
            folder = digest_dir(items, "2026-09-25", root)
            self.assertEqual(folder, root / "digests" / "2026-09-25-alpha-post-and-1-more")
            meta = json.loads((folder / "metadata.json").read_text())
            self.assertEqual((meta["kind"], meta["title"], meta["items"]), ("digest", "Alpha Post · Beta", items))
            self.assertEqual(digest_dir(items, "2026-09-25", root), folder)  # same items, same day
            other = digest_dir([items[0], {"title": "Gamma", "dir": "/c"}], "2026-09-25", root)
            self.assertNotEqual(other, folder)  # same slug, other items
            self.assertTrue(other.name.startswith("2026-09-25-alpha-post-and-1-more-"))
            many = digest_dir([{"title": t} for t in "ABCD"], "2026-09-25", root)
            self.assertEqual(json.loads((many / "metadata.json").read_text())["title"], "A · B and 2 more")
            fixed = digest_dir(items, "2026-09-25", folder=root / "x" / "_digests" / "pl", title="PL", channel="c")
            self.assertEqual(json.loads((fixed / "metadata.json").read_text())["channel"], "c")


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Unit tests for x/prepare.py (offline: recorded FxTwitter answers, the video source mocked)."""
import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.append(str(HERE.parent / "shared"))

import prepare  # noqa: E402
from _common import SkillError  # noqa: E402
from fake_fx import FX, ROOT, SECOND, VIDEO, fake, load  # noqa: E402


def args(post: str, **kw) -> argparse.Namespace:
    return argparse.Namespace(**({"post": post, "refresh": False, "max_replies": 200, "skip_download": False,
                                  "no_video": False} | kw))


def status(**kw) -> dict:
    return {"id": "1", "url": "https://x.com/a/status/1", "text": "hello", "author": {"screen_name": "a"},
            "created_timestamp": 1790196319} | kw


class TestText(unittest.TestCase):
    def test_title(self):
        self.assertEqual(prepare.title_of(status(text="@b @c Short one https://t.co/x")), "Short one")
        long = status(text="word " * 40)
        self.assertTrue(prepare.title_of(long).endswith("word…"))
        self.assertLessEqual(len(prepare.title_of(long)), prepare.TITLE_CHARS + 1)
        self.assertEqual(prepare.title_of(status(text="https://t.co/only")), "Post by @a")
        self.assertEqual(prepare.title_of(status(article={"title": "An X article"})), "An X article")

    def test_reply_text_drops_the_leading_mentions(self):
        self.assertEqual(prepare.reply_text(status(text="@a @b yes, @c agrees", replying_to={"status": "0"})),
                         "yes, @c agrees")
        self.assertEqual(prepare.reply_text(status(text="@a starts a post")), "@a starts a post")

    def test_post_block_with_quote_media_poll_card_and_note(self):
        s = status(
            likes=1200, views=5, text="line one\nline two",
            quote=status(id="2", url="https://x.com/q/status/2", text="quoted\ntext", author={"screen_name": "q"}),
            media={"photos": [{"type": "photo", "url": "https://pbs.twimg.com/p.jpg", "altText": "a chart"}],
                   "videos": [{"type": "video", "url": "https://video.twimg.com/v.mp4", "duration": 92.6}]},
            poll={"total_votes": 10, "choices": [{"label": "Yes", "percentage": 70}, {"label": "No",
                                                                                      "percentage": 30}]},
            card={"url": "https://example.com", "title": "Example", "description": "a page"},
            community_note={"text": "Readers added context.\nSecond line."})
        block = prepare.post_block(s, 1, 2, None)
        for want in ("### 1/2 [→](https://x.com/a/status/1) · 2026-09-23 · 1,200 likes, 5 views",
                     "line one\nline two",
                     "> Quoting **@q** [→](https://x.com/q/status/2) (2026-09-23):\n> quoted\n> text",
                     "- [photo 1](https://pbs.twimg.com/p.jpg): a chart",
                     "- [video 1 (01:32)](https://video.twimg.com/v.mp4)",
                     "Poll (10 votes):\n- Yes: 70%\n- No: 30%",
                     "Link card: [Example](https://example.com): a page",
                     "**Community note:** Readers added context.\n  Second line."):
            self.assertIn(want, block)

    def test_unavailable_quote(self):
        block = prepare.post_block(status(quote={"type": "tombstone", "reason": "deleted"}), 1, 1, None)
        self.assertIn("> Quoted post unavailable: deleted", block)

    def test_focus_marks_the_linked_post(self):
        self.assertIn("(the linked post)", prepare.post_block(status(), 2, 2, "1"))
        self.assertNotIn("(the linked post)", prepare.post_block(status(), 1, 1, "1"))


class TestReplies(unittest.TestCase):
    def test_nesting_order_and_thread_positions(self):
        thread = [status(id="1"), status(id="2")]
        replies = [
            status(id="10", likes=1, text="@a low", replying_to={"status": "1"}, author={"screen_name": "x"}),
            status(id="11", likes=9, text="@a high\nsecond line", replying_to={"status": "1"},
                   author={"screen_name": "y"}),
            status(id="12", likes=0, text="@y answer", replying_to={"status": "11"}, author={"screen_name": "a"},
                   created_timestamp=5),
            status(id="13", likes=2, text="@a on two", replying_to={"status": "2"}, author={"screen_name": "z"}),
            status(id="2", text="the thread's own post"),  # never listed as a reply
        ]
        text, n = prepare.replies_md(replies, thread)
        self.assertEqual(n, 4)
        lines = [line for line in text.splitlines() if line.startswith("- ")]
        self.assertEqual([line.split("**")[1] for line in lines], ["@y", "@a", "@z", "@x"])
        self.assertIn("(9 likes): high\n  second line", text)
        self.assertIn("(0 likes, reply to @y): answer", text)
        self.assertIn("(2 likes, on post 2/2): on two", text)
        self.assertIn("(1 like): low", text)


class PrepareCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = mock.patch.dict(os.environ, {"TELL_ME_ROOT": self.tmp.name})
        env.start()
        self.addCleanup(env.stop)

    def run_prepare(self, a: argparse.Namespace, fx=None) -> dict:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            prepare.prepare(a, fx or fake())
        return json.loads(out.getvalue())


class TestPrepareThread(PrepareCase):
    def test_thread_with_replies(self):
        env = self.run_prepare(args(f"https://x.com/simonw/status/{ROOT}"))
        folder = Path(env["dir"])
        self.assertEqual(folder.relative_to(self.tmp.name).parts[:3], ("posts", "x", "simonw"))
        self.assertTrue(folder.name.endswith(f"-{ROOT}"))
        self.assertEqual((env["source"], env["kind"], env["id"], env["posts"], env["focus_post"]),
                         ("x", "post", ROOT, 2, None))
        self.assertTrue(env["subskill"].endswith("subskills/x/SUBSKILL.md"))
        content = (folder / "content.md").read_text()
        self.assertIn(f"### 1/2 [→](https://x.com/simonw/status/{ROOT})", content)
        self.assertIn(f"### 2/2 [→](https://x.com/simonw/status/{SECOND})", content)
        self.assertIn("- posted by: Simon Willison (@simonw)", content)
        self.assertIn("**@simonw** [→](https://x.com/simonw/status/2102866084256956828) (9 likes, reply to "
                      "@dr_nikhilshah): It outputs a .wav file", content)
        self.assertNotIn("## Video", content)
        self.assertNotIn(": @simonw ", content)  # the reply mentions are dropped
        meta = json.loads((folder / "metadata.json").read_text())
        self.assertEqual((meta["source"], meta["site"], meta["extractor"], meta["content_file"]),
                         ("x", "X", "fxtwitter", "content.md"))
        self.assertEqual(meta["extras"]["replies_fetched"], env["replies_fetched"])
        self.assertGreater(env["replies_fetched"], 30)
        self.assertEqual(meta["published"], "2026-09-23")
        self.assertGreater(meta["word_count"], 100)

    def test_a_later_post_prepares_the_thread_and_is_reused_by_its_id(self):
        env = self.run_prepare(args(f"https://x.com/simonw/status/{SECOND}"))
        self.assertEqual((env["id"], env["focus_post"]), (ROOT, SECOND))
        content = Path(env["content_file"]).read_text()
        self.assertIn("(the linked post)", content)
        meta = json.loads((Path(env["dir"]) / "metadata.json").read_text())
        self.assertEqual(meta["extras"]["aliases"], [SECOND])
        # both links now reuse the folder without a request
        for link, focus in ((SECOND, SECOND), (ROOT, None)):
            fx = fake()
            again = self.run_prepare(args(link), fx)
            self.assertEqual((again["dir"], again["reused"], again["focus_post"]), (env["dir"], True, focus))
            self.assertEqual(fx.get.calls, [])

    def test_refresh_refetches_into_the_same_folder(self):
        env = self.run_prepare(args(ROOT))
        again = self.run_prepare(args(ROOT, refresh=True, max_replies=0))
        self.assertEqual((again["dir"], again["reused"], again["replies_fetched"]), (env["dir"], True, 0))
        self.assertIn("*No replies fetched.*", Path(again["content_file"]).read_text())

    def test_a_reply_to_someone_else_gets_that_post_as_context(self):
        reply = load("conversation.likes.json")["replies"][1]  # @dr_nikhilshah's reply to simonw
        fx = fake({f"{FX}thread/{reply['id']}": {"code": 200, "status": reply, "thread": [reply]}})
        env = self.run_prepare(args(reply["id"], max_replies=0), fx)
        content = Path(env["content_file"]).read_text()
        self.assertIn(f"## In reply to\n\n### [→](https://x.com/simonw/status/{ROOT})", content)
        self.assertIn("Could not find if it generates an mp3 file", content)

    def test_not_an_x_post(self):
        with self.assertRaisesRegex(SkillError, "not an x.com post"):
            self.run_prepare(args("https://example.com/a"))


class TestVideoPart(PrepareCase):
    def fake_video(self, returncode=0):
        """subprocess.run standing in for video/prepare.py --content-part video."""
        def run(cmd, **kw):
            self.cmd = cmd
            folder = Path(cmd[cmd.index("--dir") + 1])
            if returncode:
                return subprocess.CompletedProcess(cmd, returncode, "", "")
            (folder / "video-transcript.md").write_text("# Clip\n\n- url: x\n\n## Transcript\n\n00:01 Bilbo spoke\n")
            meta = json.loads((folder / "metadata.json").read_text())
            assert meta["source"] == "x" and meta["title"]  # the owner fields exist before the download tags
            meta["video"] = {"transcript_file": "video-transcript.md", "transcript_source": "captions"}
            (folder / "metadata.json").write_text(json.dumps(meta))
            out = {"part": "video", "transcript": str(folder / "video-transcript.md"), "duration": "01:32",
                   "transcript_source": "captions"}
            return subprocess.CompletedProcess(cmd, 0, json.dumps(out), "")
        return mock.patch.object(prepare.subprocess, "run", side_effect=run)

    def test_the_transcript_becomes_the_video_part(self):
        with self.fake_video():
            env = self.run_prepare(args(VIDEO))
        self.assertEqual(self.cmd[1:], [str(prepare.VIDEO_PREPARE), f"https://x.com/karpathy/status/{VIDEO}",
                                        "--dir", env["dir"], "--content-part", "video"])
        content = Path(env["content_file"]).read_text()
        self.assertIn("## Video\n\nThe video of [post", content)
        self.assertIn("00:01 Bilbo spoke\n\n## Replies", content)
        self.assertTrue(env["video_transcript"].endswith("video-transcript.md"))
        meta = json.loads((Path(env["dir"]) / "metadata.json").read_text())
        self.assertEqual(meta["video"]["transcript_source"], "captions")  # kept by the final metadata write

    def test_skip_download_and_no_video(self):
        with self.fake_video():
            self.run_prepare(args(VIDEO, skip_download=True))
        self.assertIn("--skip-download", self.cmd)
        with mock.patch.object(prepare.subprocess, "run") as run:
            env = self.run_prepare(args(VIDEO, refresh=True, no_video=True))
        run.assert_not_called()
        self.assertNotIn("## Video", Path(env["content_file"]).read_text())

    def test_missing_video_tools_are_noted_not_fatal(self):
        with self.fake_video(returncode=2):
            env = self.run_prepare(args(VIDEO))
        self.assertIn("install-prerequisites.sh", env["attempts"][-1])
        self.assertIn("its transcript was skipped", Path(env["content_file"]).read_text())

    def test_a_failing_video_source_is_noted(self):
        with self.fake_video(returncode=1):
            env = self.run_prepare(args(VIDEO))
        self.assertIn("video source failed", env["attempts"][-1])

    def test_gifs_have_no_video_part(self):
        gif = {"media": {"videos": [{"type": "gif", "url": "g"}]}}
        self.assertIsNone(prepare.first_video([status(**gif)]))
        self.assertEqual(prepare.first_video([status(), status(id="2", media={"videos": [{"type": "video"}]})])["id"],
                         "2")


if __name__ == "__main__":
    unittest.main()

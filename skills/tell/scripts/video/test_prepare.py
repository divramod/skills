#!/usr/bin/env python3
"""Unit tests for video/prepare.py (offline)."""
import unittest

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

from _common import fmt_ts, parse_ts
from prepare import group_paragraphs, parse_vtt, pick_track

ROLLING_AUTO_VTT = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:02.500 align:start position:0%

hello<00:00:00.500><c> world</c>

00:00:02.500 --> 00:00:02.510 align:start position:0%
hello world


00:00:02.510 --> 00:00:05.000 align:start position:0%
hello world
this<00:00:03.000><c> is</c><00:00:03.400><c> a &amp; test</c>
"""


class TestTimestamps(unittest.TestCase):
    def test_fmt(self):
        self.assertEqual(fmt_ts(5), "00:05")
        self.assertEqual(fmt_ts(3725.9), "1:02:05")

    def test_parse(self):
        self.assertEqual(parse_ts("00:01:02.500"), 62.5)
        self.assertEqual(parse_ts("01:02,000"), 62.0)


class TestParseVtt(unittest.TestCase):
    def test_rolling_captions_are_deduplicated_and_untagged(self):
        self.assertEqual(
            parse_vtt(ROLLING_AUTO_VTT),
            [(0.0, "hello world"), (2.51, "this is a & test")],
        )

    def test_header_is_ignored(self):
        self.assertEqual(parse_vtt("WEBVTT\nKind: captions\n"), [])


class TestPickTrack(unittest.TestCase):
    def test_manual_beats_auto(self):
        info = {"subtitles": {"de": [1], "en": [1]}, "automatic_captions": {"en-orig": [1]}, "language": "en"}
        self.assertEqual(pick_track(info, None), ("en", False))

    def test_wanted_lang_manual(self):
        info = {"subtitles": {"de": [1], "en": [1]}, "language": "en"}
        self.assertEqual(pick_track(info, "de"), ("de", False))

    def test_auto_prefers_orig_track(self):
        info = {"subtitles": {}, "automatic_captions": {"de": [1], "en": [1], "en-orig": [1]}, "language": "en"}
        self.assertEqual(pick_track(info, None), ("en-orig", True))

    def test_orig_language_inferred_from_orig_track(self):
        info = {"automatic_captions": {"en": [1], "fr": [1], "fr-orig": [1]}}
        self.assertEqual(pick_track(info, None), ("fr-orig", True))

    def test_region_prefix_match(self):
        info = {"subtitles": {"en-US": [1]}}
        self.assertEqual(pick_track(info, "en"), ("en-US", False))

    def test_live_chat_ignored_and_none_when_empty(self):
        self.assertIsNone(pick_track({"subtitles": {"live_chat": [1]}}, None))
        self.assertIsNone(pick_track({}, None))


class TestGroupParagraphs(unittest.TestCase):
    def test_splits_by_time(self):
        lines = [(0, "a"), (10, "b"), (31, "c")]
        self.assertEqual(group_paragraphs(lines, seconds=30), "[00:00] a b\n\n[00:31] c")

    def test_chapter_headings(self):
        lines = [(0, "a"), (6, "b"), (7, "c")]
        chapters = [{"start_time": 0, "title": "Intro"}, {"start_time": 5, "title": "Main"}]
        self.assertEqual(
            group_paragraphs(lines, chapters),
            "### Intro (00:00)\n\n[00:00] a\n\n### Main (00:05)\n\n[00:06] b c",
        )

    def test_custom_link_renderer(self):
        out = group_paragraphs([(44, "x")], link=lambda s: f"L{int(s)}")
        self.assertEqual(out, "[L44] x")


class TestDownloadPlan(unittest.TestCase):
    def test_downloads_best_in_background_by_default(self):
        from prepare import download_plan
        self.assertEqual(download_plan(False, False, None, False), ("background", "best"))
        self.assertEqual(download_plan(False, False, "1080p", True), ("background", "best"))  # upgrade
        self.assertEqual(download_plan(False, False, "best", True), (None, "best"))

    def test_skip_download_and_visual(self):
        from prepare import download_plan
        self.assertEqual(download_plan(True, False, None, False), (None, "1080p"))
        self.assertEqual(download_plan(False, True, None, False), ("wait", "best"))
        self.assertEqual(download_plan(True, True, None, False), ("wait", "1080p"))


class TestDescriptionLinks(unittest.TestCase):
    def test_groups_repos_slides_and_drops_noise(self):
        from prepare import description_links
        desc = """Code: https://github.com/unslothai/unsloth and https://github.com/unslothai/unsloth.
Slides (PDF): https://cs229.stanford.edu/lectures/lecture1.pdf
Deck https://speakerdeck.com/tim/fine-tuning
Model https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct
Docs: https://docs.unsloth.ai/get-started.
Follow me https://twitter.com/tim and https://www.youtube.com/@TechWithTim
Profile https://github.com/techwithtim"""
        self.assertEqual(description_links(desc), {
            "repos": ["https://github.com/unslothai/unsloth", "https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct"],
            "slides": ["https://cs229.stanford.edu/lectures/lecture1.pdf", "https://speakerdeck.com/tim/fine-tuning"],
            "other": ["https://docs.unsloth.ai/get-started", "https://github.com/techwithtim"],
        })
        self.assertEqual(description_links(None), {"repos": [], "slides": [], "other": []})


class TestRenderTranscript(unittest.TestCase):
    def test_chapters_and_paragraphs_carry_youtube_links(self):
        from _common import ts_link
        from prepare import render_transcript
        info = {"id": "abc", "extractor_key": "Youtube", "title": "T", "duration": 70,
                "chapters": [{"start_time": 42, "title": "Main"}]}
        body = group_paragraphs([(44, "x")], link=lambda s: ts_link(info, s))
        md = render_transcript(info, "captions", body)
        self.assertIn("- [00:42](https://www.youtube.com/watch?v=abc&t=42s) Main", md)
        self.assertIn("[[00:44](https://www.youtube.com/watch?v=abc&t=44s)] x", md)

    def test_unknown_duration_is_not_zero(self):
        from prepare import render_transcript
        self.assertIn("- duration: ?", render_transcript({"title": "T"}, "whisper", "x"))


class TestPickEntry(unittest.TestCase):
    """A post with several videos: yt-dlp answers a playlist even with --no-playlist (no duration, no captions)."""
    POST = {"_type": "playlist", "id": "1578401165338976258", "webpage_url": "https://x.com/p/status/1578401165338976258",
            "uploader": "Prime", "upload_date": "20221007",
            "entries": [{"id": "a", "duration": 6.006, "title": "T"}, {"id": "b", "duration": 7.5, "title": "T #2"}]}

    def test_a_single_video_passes_through(self):
        from prepare import pick_entry
        info = {"id": "v", "duration": 3}
        self.assertEqual(pick_entry(info, 1), (info, None, 1))

    def test_the_chosen_entry_with_the_posts_facts(self):
        from prepare import pick_entry
        entry, item, videos = pick_entry(self.POST, 2)
        self.assertEqual((entry["id"], entry["duration"], item, videos), ("b", 7.5, 2, 2))
        self.assertEqual((entry["webpage_url"], entry["uploader"]), (self.POST["webpage_url"], "Prime"))
        self.assertEqual(pick_entry(self.POST, 9)[:2], (self.POST["entries"][0] | {
            k: self.POST[k] for k in ("webpage_url", "uploader", "upload_date")}, 1))

    def test_an_empty_playlist_fails(self):
        from _common import SkillError
        from prepare import pick_entry
        with self.assertRaises(SkillError):
            pick_entry({"_type": "playlist", "entries": []}, 1)

    def test_every_later_ytdlp_call_takes_the_item(self):
        import argparse
        from prepare import ytdlp
        self.assertEqual(ytdlp(argparse.Namespace(cookies_from_browser=None, item=2))[-2:], ["--playlist-items", "2"])
        self.assertNotIn("--playlist-items", ytdlp(argparse.Namespace(cookies_from_browser=None, item=None)))


class TestContractFields(unittest.TestCase):
    def test_video_contract_fields(self):
        import tempfile
        from _common import CONTRACT_KEYS
        from prepare import contract_fields
        with tempfile.TemporaryDirectory() as tmp:
            transcript = Path(tmp) / "transcript.md"
            transcript.write_text("a b c d")
            info = {"id": "abc", "extractor_key": "Youtube", "title": "T", "channel": "Chan", "upload_date": "20260101",
                    "webpage_url": "https://www.youtube.com/watch?v=abc", "view_count": 5, "chapters": [{}]}
            fields = contract_fields(info, "captions (manual, en)", "2026-09-25T10:00:00", transcript)
        self.assertEqual(fields, {
            "source": "video", "url": "https://www.youtube.com/watch?v=abc", "author": "Chan", "published": "2026-01-01",
            "fetched": "2026-09-25T10:00:00", "site": "youtube", "word_count": 4, "extractor": "captions (manual, en)",
            "content_file": "transcript.md", "extras": {"views": 5, "chapters": 1}})
        # with id/title/duration from META_KEYS every contract key is present
        self.assertEqual(set(CONTRACT_KEYS) - set(fields), {"id", "title", "duration"})


class TestContentPart(unittest.TestCase):
    """--dir/--content-part: the video of another item (an x post) goes into that item's folder."""

    def run_part(self, folder: Path, *extra: str, info: dict | None = None,
                 url: str = "https://x.com/u/status/99") -> tuple[dict, str]:
        import contextlib
        import io
        import json
        from unittest import mock

        import prepare
        info = info or {"id": "99", "title": "Clip", "duration": 92, "webpage_url": "https://x.com/u/status/99",
                        "extractor_key": "Twitter", "uploader": "u"}
        out = io.StringIO()
        with mock.patch.object(prepare, "require"), \
                mock.patch.object(prepare, "fetch_info", return_value=info), \
                mock.patch.object(prepare, "fetch_transcript", return_value=([(0.0, "hello there")], "captions")) as ft, \
                mock.patch.object(prepare, "start_background", return_value={"status": "running"}) as bg, \
                mock.patch.object(prepare, "find_existing", side_effect=AssertionError("no library lookup")), \
                contextlib.redirect_stdout(out):
            prepare.main([url, "--dir", str(folder), "--content-part", "video", *extra])
        self.calls = (ft.call_count, bg.call_count)
        self.bg_args = bg.call_args
        self.ft_args = ft.call_args
        return json.loads(out.getvalue()), (folder / "video-transcript.md").read_text()

    def test_writes_into_the_given_folder_without_touching_the_owner_fields(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "posts" / "x" / "u" / "clip-99"
            folder.mkdir(parents=True)
            (folder / "metadata.json").write_text(json.dumps({"source": "x", "id": "99", "title": "A post"}))
            out, text = self.run_part(folder)
            meta = json.loads((folder / "metadata.json").read_text())
            self.assertEqual(self.calls, (1, 1))  # transcript + background download
            self.assertFalse((folder / "content.md").exists())
            self.assertIn("## Transcript", text)
            self.assertIn("hello there", text)
            self.assertEqual((meta["source"], meta["id"], meta["title"]), ("x", "99", "A post"))
            self.assertEqual(meta["video"]["transcript_source"], "captions")
            self.assertEqual(meta["video"]["transcript_file"], "video-transcript.md")
            self.assertEqual((out["part"], out["transcript_source"], out["duration"]), ("video", "captions", "01:32"))
            self.assertEqual(list(Path(tmp).glob("videos")), [])  # no library entry of its own
            # a second run reuses the transcript; --skip-download starts no download
            out, _ = self.run_part(folder, "--skip-download")
            self.assertEqual(self.calls, (0, 0))

    def folder(self, tmp: str, meta: dict | None = None) -> Path:
        import json
        folder = Path(tmp) / "posts" / "x" / "u" / "clip-99"
        folder.mkdir(parents=True)
        (folder / "metadata.json").write_text(json.dumps({"source": "x", "id": "99", "title": "A post"}
                                                         if meta is None else meta))
        return folder

    def test_one_video_of_a_post_with_several(self):
        import json
        import tempfile
        info = TestPickEntry.POST
        with tempfile.TemporaryDirectory() as tmp:
            folder = self.folder(tmp)
            out, text = self.run_part(folder, "--playlist-item", "2", info=info, url=info["webpage_url"])
            self.assertEqual((out["videos"], out["playlist_item"], out["duration"], out["duration_seconds"]),
                             (2, 2, "00:07", 7.5))
            self.assertIn("- duration: 00:07", text)
            self.assertEqual(self.bg_args.args[-1], 2)  # the download takes video 2 only
            self.assertEqual(self.ft_args.args[0].item, 2)  # and so do captions / Whisper
            meta = json.loads((folder / "metadata.json").read_text())
            self.assertEqual((meta["video"]["playlist_item"], meta["video"]["videos"]), (2, 2))
            # the same video again: the transcript is reused; another one is transcribed
            self.run_part(folder, "--skip-download", "--playlist-item", "2", info=info, url=info["webpage_url"])
            self.assertEqual(self.calls, (0, 0))
            self.run_part(folder, "--skip-download", info=info, url=info["webpage_url"])
            self.assertEqual(self.calls, (1, 0))

    def test_another_url_is_transcribed_anew(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            folder = self.folder(tmp)
            self.run_part(folder, "--skip-download")
            self.run_part(folder, "--skip-download", url="https://x.com/u/status/100")
            self.assertEqual(self.calls, (1, 0))

    def test_part_needs_the_owners_folder(self):
        import tempfile
        from _common import SkillError
        with tempfile.TemporaryDirectory() as tmp:
            for meta in ({}, {"source": "x"}, {"title": "T"}):
                folder = Path(tmp) / str(len(list(Path(tmp).iterdir())))
                folder.mkdir()
                if meta:
                    (folder / "metadata.json").write_text(__import__("json").dumps(meta))
                with self.assertRaisesRegex(SkillError, "prepared item's folder"):
                    self.run_part(folder)

    def test_dir_needs_content_part(self):
        from _common import SkillError
        import prepare
        with self.assertRaises(SkillError):
            prepare.main(["https://x.com/u/status/99", "--dir", "/tmp"])


if __name__ == "__main__":
    unittest.main()

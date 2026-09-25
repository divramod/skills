#!/usr/bin/env python3
"""Unit tests for fetch_transcript.py (offline). Run: python3 -m unittest test_fetch_transcript.py"""
import unittest

from fetch_transcript import fmt_ts, group_paragraphs, parse_ts, parse_vtt, pick_track

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


if __name__ == "__main__":
    unittest.main()

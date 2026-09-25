#!/usr/bin/env python3
"""Unit tests for extract_frames.py (offline)."""
import unittest

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

from extract_frames import interval_seconds, min_scene_frames, parse_showinfo, render_index, sample_indices

SHOWINFO = """\
[Parsed_showinfo_1 @ 0x1] config in time_base: 1/15360
[Parsed_showinfo_1 @ 0x1] n:   0 pts:      0 pts_time:0       duration:512
[Parsed_showinfo_1 @ 0x1] n:   1 pts: 153600 pts_time:10      duration:512
[Parsed_showinfo_1 @ 0x1] n:   2 pts: 399360 pts_time:26.5    duration:512
frame=    3 fps=0.0 q=3.0
"""


class TestFrames(unittest.TestCase):
    def test_parse_showinfo(self):
        self.assertEqual(parse_showinfo(SHOWINFO), [0.0, 10.0, 26.5])

    def test_sample_keeps_all_when_under_cap(self):
        self.assertEqual(sample_indices(3, 40), [0, 1, 2])

    def test_sample_spreads_evenly_and_keeps_ends(self):
        idx = sample_indices(100, 5)
        self.assertEqual(len(idx), 5)
        self.assertEqual((idx[0], idx[-1]), (0, 99))

    def test_interval(self):
        self.assertEqual(interval_seconds(400, 40), 10)
        self.assertEqual(interval_seconds(10, 40), 1.0)

    def test_min_scene_frames_scales_with_duration(self):
        self.assertEqual(min_scene_frames(12, 4), 2)
        self.assertEqual(min_scene_frames(90, 4), 3)
        self.assertEqual(min_scene_frames(3600, 4), 4)

    def test_index_links(self):
        md = render_index({"extractor_key": "Youtube", "id": "abc", "title": "T"}, [("001.jpg", 10.0)], "scene>0.3")
        self.assertIn("| 1 | [00:10](https://www.youtube.com/watch?v=abc&t=10s) | ![00:10](001.jpg) |", md)


if __name__ == "__main__":
    unittest.main()

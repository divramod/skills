#!/usr/bin/env python3
"""Unit tests for speech_text.py (offline)."""
import unittest

from speech_text import speech_text, text_hash

NOTE = """---
title: "T"
lang: "en"
---

# The title

Ann · 12:09 · 2026-09-24 · https://www.youtube.com/watch?v=abc

**TL;DR:** It *works* with [Kokoro](https://github.com/x/kokoro) *(v1.0 released 2026-09-01 · last commit 2026-09-24 on main)* and `uv` ([00:44](https://www.youtube.com/watch?v=abc&t=44s), [¶3](https://a.b/#p3)).
See https://example.com for more.

<!-- a comment
over two lines -->

## Key points

- First point ([→](https://x.com/a/status/1))
- Second point!
1. Numbered

| a | b |
|---|---|
| 1 | 2 |

```bash
rm -rf /
```

> A quote ([L42](https://github.com/o/r/blob/x#L42))

![frame](frames/001.jpg)

## Links

- [Something](https://example.com): never read
"""


class TestSpeechText(unittest.TestCase):
    def setUp(self):
        self.text = speech_text(NOTE)
        self.paragraphs = self.text.split("\n\n")

    def test_title_but_not_the_info_line(self):
        self.assertEqual(self.paragraphs[0], "The title.")
        self.assertNotIn("12:09", self.text)

    def test_links_read_as_labels_anchors_urls_and_dates_dropped(self):
        self.assertIn("TL;DR: It works with Kokoro and uv.", self.text)
        self.assertIn("See for more.", self.text)
        for gone in ("http", "¶", "→", "L42", "released", "(", "*", "`"):
            self.assertNotIn(gone, self.text)

    def test_list_items_are_sentences_of_their_own(self):
        self.assertIn("First point.", self.paragraphs)
        self.assertIn("Second point!", self.paragraphs)
        self.assertIn("Numbered.", self.paragraphs)
        self.assertIn("Key points.", self.paragraphs)

    def test_code_tables_comments_images_dropped(self):
        for gone in ("rm -rf", "| a", "comment", "frame"):
            self.assertNotIn(gone, self.text)
        self.assertIn("A quote", self.text)

    def test_stops_at_the_links_section(self):
        self.assertNotIn("Links", self.text)
        self.assertNotIn("never read", self.text)
        self.assertNotIn("Similar", speech_text("## Point\n\nyes\n\n## Similar videos\n\n- a"))

    def test_hash_follows_the_text(self):
        self.assertEqual(text_hash(self.text), text_hash(speech_text(NOTE)))
        self.assertNotEqual(text_hash(self.text), text_hash(speech_text(NOTE.replace("Second", "Other"))))


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Unit tests for check_links.py (offline)."""
import unittest

from check_links import classify, extract_links

BODY = """**TL;DR:** x ([00:44](https://www.youtube.com/watch?v=abc&t=44s))

## Links
- [Thinking, Fast and Slow](https://www.amazon.com/dp/0374533555): Kahneman's System 1/2 book
- [LoRA](https://en.wikipedia.org/wiki/Fine-tuning_(deep_learning)): low-rank adaptation
- Site: https://typesafe.ai.
- <https://unsloth.ai/docs>
- again [LoRA](https://en.wikipedia.org/wiki/Fine-tuning_(deep_learning))
"""


class TestCheckLinks(unittest.TestCase):
    def test_extract_skips_video_timestamps_and_dedupes(self):
        self.assertEqual(extract_links(BODY), [
            "https://www.amazon.com/dp/0374533555",
            "https://en.wikipedia.org/wiki/Fine-tuning_(deep_learning)",
            "https://typesafe.ai",
            "https://unsloth.ai/docs",
        ])

    def test_classify(self):
        self.assertEqual(classify(200), "ok")
        self.assertEqual(classify(301), "ok")
        self.assertEqual(classify(404), "broken")
        self.assertEqual(classify(503), "unverified")  # Amazon bot wall
        self.assertEqual(classify(None, "timed out"), "unverified")
        self.assertEqual(classify(None, "[Errno 8] nodename nor servname provided"), "broken")


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Unit tests for link_dates.py and check_links.annotate (offline)."""
import unittest
from unittest import mock

import link_dates
from check_links import annotate
from link_dates import date_info, day, page_dates, youtube_id


class TestHelpers(unittest.TestCase):
    def test_day(self):
        self.assertEqual(day("2025-06-03T10:00:00Z"), "2025-06-03")
        self.assertEqual(day("20250603"), "2025-06-03")
        self.assertEqual(day("2011"), "2011")
        self.assertEqual(day("2013-4"), "2013-04")
        self.assertEqual(day("1734591637"), "2024-12-19")  # og:updated_time in epoch seconds
        self.assertEqual(day("1734591637000"), "2024-12-19")  # ... or milliseconds
        self.assertEqual(day("Oct 25, 2011"), "2011")
        self.assertEqual(day(0), "1970-01-01")
        self.assertIsNone(day(None))

    def test_youtube_id(self):
        self.assertEqual(youtube_id("https://www.youtube.com/watch?v=abc123XYZ&t=5s"), "abc123XYZ")
        self.assertEqual(youtube_id("https://youtu.be/abc123XYZ"), "abc123XYZ")
        self.assertEqual(youtube_id("https://www.youtube.com/shorts/abc123XYZ"), "abc123XYZ")
        self.assertIsNone(youtube_id("https://www.youtube.com/@TechWithTim"))
        self.assertIsNone(youtube_id("https://example.com/watch?v=x"))


class TestPageDates(unittest.TestCase):
    def test_opengraph_and_jsonld(self):
        html = ('<meta property="article:published_time" content="2025-01-10T08:00:00+00:00">'
                '<script type="application/ld+json">{"dateModified": "2025-03-02"}</script>')
        self.assertEqual(page_dates(html)["label"], "published 2025-01-10 · updated 2025-03-02")

    def test_same_dates_collapse(self):
        html = '<meta itemprop="datePublished" content="2025-01-10"><meta itemprop="dateModified" content="2025-01-10">'
        self.assertEqual(page_dates(html)["label"], "published 2025-01-10")

    def test_embedded_json_and_text_fallbacks(self):
        self.assertEqual(page_dates('{"date","2026-09-15T00:00:00.000Z"}'.replace('","', '": "'))["label"],
                         "published 2026-09-15")
        self.assertEqual(page_dates("<p>Posted Sep 15, 2026 by X</p>")["label"], "dated 2026-09-15")
        self.assertEqual(page_dates("<p>15 March 2024</p>")["published"], "2024-03-15")
        self.assertEqual(page_dates("<p>Sep 15, 2026</p>", homepage=True), {})
        self.assertEqual(page_dates("<p>nothing</p>"), {})


class TestDispatch(unittest.TestCase):
    def test_routes_by_host(self):
        calls = {}
        fakes = {name: (lambda n: lambda *a: calls.setdefault(n, a) and {"label": n})(name)
                 for name in ("github", "arxiv", "crossref", "book", "wikipedia", "pypi", "npm", "huggingface")}
        with mock.patch.multiple(link_dates, **fakes), mock.patch.object(link_dates, "get", return_value="<p/>"):
            date_info("https://github.com/unslothai/unsloth/tree/main")
            date_info("https://arxiv.org/pdf/2106.09685v2.pdf")
            date_info("https://doi.org/10.1038/nature14539")
            date_info("https://www.amazon.com/Thinking-Fast-Slow/dp/0374533555/ref=x")
            date_info("https://en.wikipedia.org/wiki/Fine-tuning_(deep_learning)")
            date_info("https://pypi.org/project/unsloth/")
            date_info("https://www.npmjs.com/package/@anthropic-ai/sdk")
            date_info("https://huggingface.co/datasets/org/data")
        self.assertEqual(calls["github"], ("unslothai", "unsloth"))
        self.assertEqual(calls["arxiv"], ("2106.09685",))
        self.assertEqual(calls["crossref"], ("10.1038/nature14539",))
        self.assertEqual(calls["book"], ("0374533555",))
        self.assertEqual(calls["wikipedia"], ("en", "Fine-tuning_(deep_learning)"))
        self.assertEqual(calls["pypi"], ("unsloth",))
        self.assertEqual(calls["npm"], ("@anthropic-ai/sdk",))
        self.assertEqual(calls["huggingface"], ("datasets", "org/data"))

    def test_youtube_uses_prefetched_dates(self):
        self.assertEqual(date_info("https://www.youtube.com/watch?v=abc", {"abc": "2025-06-03"})["label"],
                         "published 2025-06-03")

    def test_network_errors_give_empty(self):
        with mock.patch.object(link_dates, "get", side_effect=OSError("down")):
            self.assertEqual(date_info("https://example.com/post"), {})


class TestAnnotate(unittest.TestCase):
    def test_inserts_and_refreshes_labels(self):
        body = ("- [Repo](https://github.com/o/r): x\n"
                "- [Vid](https://www.youtube.com/watch?v=abc) *(published 2020-01-01)*: y\n"
                "- [Unknown](https://example.com): z ([00:05](https://www.youtube.com/watch?v=me&t=5s))\n")
        out = annotate(body, {"https://github.com/o/r": "v1 released 2026-01-01",
                              "https://www.youtube.com/watch?v=abc": "published 2025-06-03"})
        self.assertIn("- [Repo](https://github.com/o/r) *(v1 released 2026-01-01)*: x", out)
        self.assertIn("- [Vid](https://www.youtube.com/watch?v=abc) *(published 2025-06-03)*: y", out)
        self.assertIn("- [Unknown](https://example.com): z", out)
        self.assertEqual(annotate(out, {"https://github.com/o/r": "v1 released 2026-01-01"}), out)  # idempotent


if __name__ == "__main__":
    unittest.main()

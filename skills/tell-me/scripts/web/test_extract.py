#!/usr/bin/env python3
"""Unit tests for web/extract.py (offline: recorded fixtures, network and tools mocked)."""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

import extract
from _common import SkillError
from extract import (Extraction, HttpError, absolutize, from_defuddle, from_jina, from_trafilatura, is_boilerplate,
                     merge_meta, normalize, pick, raw_snapshot, score, word_count)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
URL = "https://simonwillison.net/2024/Dec/19/one-shot-python-tools/"
TITLE = "Building Python tools with a one-shot prompt using uv run and Claude Projects"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def traf() -> Extraction:
    return from_trafilatura(fixture("post.trafilatura.md"))


def defu() -> Extraction:
    return from_defuddle(fixture("post.defuddle.json"))


class TestParsers(unittest.TestCase):
    def test_trafilatura_frontmatter_and_repeated_title(self):
        ex = traf()
        self.assertEqual(ex.extractor, "trafilatura")
        self.assertEqual(ex.meta["title"], TITLE)
        self.assertEqual(ex.meta["published"], "2024-12-19")
        self.assertEqual(ex.meta["site"], "Simon Willison’s Weblog")
        self.assertEqual(ex.meta["url"], URL)
        self.assertFalse(ex.markdown.startswith("#"), "the title heading is dropped from the body")

    def test_trafilatura_without_frontmatter(self):
        ex = from_trafilatura("just text\n")
        self.assertEqual((ex.markdown, ex.meta["title"]), ("just text", None))

    def test_defuddle_json(self):
        ex = defu()
        self.assertEqual(ex.extractor, "defuddle")
        self.assertEqual(ex.meta["author"], "Simon Willison")
        self.assertEqual(ex.meta["language"], "en-gb")
        self.assertIsNone(ex.meta["published"], "empty published stays empty")
        self.assertIn("```", ex.markdown)

    def test_defuddle_schema_org_date_is_cut_to_day(self):
        ex = from_defuddle('{"content": "x", "schemaOrgData": {"datePublished": "2025-01-02T10:00:00Z", '
                           '"headline": "H"}}')
        self.assertEqual((ex.meta["published"], ex.meta["title"]), ("2025-01-02", "H"))

    def test_jina_header_and_fetch_time_ignored(self):
        ex = from_jina(fixture("post.jina.txt"))
        self.assertEqual(ex.meta, {"title": TITLE, "url": URL})
        self.assertNotIn("Markdown Content:", ex.markdown)
        self.assertTrue(ex.markdown.startswith("19th December 2024"))

    def test_jina_without_header(self):
        self.assertEqual(from_jina("plain body").markdown, "plain body")


class TestScoring(unittest.TestCase):
    def test_defuddle_wins_on_the_recorded_post(self):
        # trafilatura has more prose words, but flattens code into prose and keeps "More recent articles"
        t, d = traf(), defu()
        self.assertGreater(t.words, d.words)
        self.assertGreater(score(d.markdown), score(t.markdown))
        self.assertEqual(pick([t, d]).extractor, "defuddle")

    def test_code_counts_as_content(self):
        prose = "one two three"
        self.assertGreater(score(prose + "\n\n```\nfour five six\n```"), score(prose))

    def test_link_list_is_boilerplate(self):
        self.assertTrue(is_boilerplate("- [First post title](https://a/1)\n- [Second post title](https://a/2)"))
        self.assertFalse(is_boilerplate("A long sentence that mentions [one link](https://a) in passing only."))
        self.assertTrue(is_boilerplate("Share this on Twitter"))

    def test_furniture_section_is_penalized(self):
        body = "word " * 50
        tail = "\n\n## More recent articles\n\nSome teaser text about another post entirely"
        self.assertLess(score(body + tail), score(body))
        self.assertEqual(score(body + "\n\n## Results\n\nsome real text"), word_count(body + " Results some real text"))

    def test_pick_merges_metadata_defuddle_first(self):
        best = pick([traf(), defu()])
        self.assertEqual(best.meta["language"], "en-gb")  # only defuddle has it
        self.assertEqual(best.meta["published"], "2024-12-19")  # defuddle's is empty: trafilatura fills it
        self.assertEqual(best.meta["url"], URL)

    def test_pick_skips_empty(self):
        self.assertIsNone(pick([Extraction(""), Extraction("")]))
        self.assertEqual(pick([Extraction("", extractor="a"), Extraction("x", extractor="b")]).extractor, "b")

    def test_merge_meta_first_non_empty(self):
        self.assertEqual(merge_meta({"a": "", "b": None}, {"a": 1, "b": []}, {"b": 2}), {"a": 1, "b": 2})


class TestAbsolutize(unittest.TestCase):
    def test_relative_targets(self):
        md = "[a](/x) ![i](img.png) [b](https://o/y) [c](#frag) [d](mailto:m@x)"
        self.assertEqual(absolutize(md, "https://h.com/blog/post"),
                         "[a](https://h.com/x) ![i](https://h.com/blog/img.png) [b](https://o/y) [c](#frag) "
                         "[d](mailto:m@x)")


class TestNormalize(unittest.TestCase):
    def test_heading_gets_its_own_block(self):
        self.assertEqual(normalize("`cmd`\n## Next\ntext\n\n\n\nmore  "), "`cmd`\n\n## Next\ntext\n\nmore")

    def test_data_links_become_text(self):
        self.assertEqual(normalize("[Download](data:text/plain,<a href=x>(1)</a> more) and [b](https://b)"),
                         "Download and [b](https://b)")
        self.assertEqual(normalize("[T](data:x,unclosed ( paren\nnext line"), "T\nnext line")

    def test_fenced_code_untouched(self):
        md = "```\n# comment\n\n\n# another\n```"
        self.assertEqual(normalize(md), md)


class TestUrls(unittest.TestCase):
    def test_raw_snapshot(self):
        self.assertEqual(raw_snapshot(SNAPSHOT), SNAPSHOT_RAW)

    def test_jina_keeps_the_app_route(self):
        with mock.patch.object(extract, "http_get", return_value=("Markdown Content:\nx", "")) as get:
            extract.jina("https://docsify.js.org/#/quickstart")
        self.assertEqual(get.call_args.args[0], "https://r.jina.ai/https://docsify.js.org/%23/quickstart")


class TestRunTool(unittest.TestCase):
    def run_with(self, **kw):
        return mock.patch.object(extract.subprocess, "run", **kw)

    def test_error_on_stdout_is_a_failure(self):
        with self.run_with(return_value=subprocess.CompletedProcess([], 0, "Error: could not parse\n", "")):
            with self.assertRaisesRegex(SkillError, "could not parse"):
                extract.run_tool("defuddle", ["npx"])

    def test_timeout(self):
        with self.run_with(side_effect=subprocess.TimeoutExpired("x", 1)):
            with self.assertRaisesRegex(SkillError, "defuddle timed out"):
                extract.run_tool("defuddle", ["npx"])

    def test_nonzero_exit_shows_last_stderr_line(self):
        with self.run_with(return_value=subprocess.CompletedProcess([], 1, "", "trace\nValueError: bad\n")):
            with self.assertRaisesRegex(SkillError, "^ValueError: bad$"):
                extract.run_tool("trafilatura", ["uvx"])


class FakeWeb:
    """Canned http_get / extractor results keyed by URL or HTML; records the call order."""

    def __init__(self, pages: dict, extractions: dict):
        self.pages, self.extractions, self.calls, self.headers = pages, extractions, [], {}

    def http_get(self, url, timeout=0, accept="", headers=None):
        self.calls.append(url)
        self.headers[url] = headers or {}
        page = self.pages.get(url)
        if isinstance(page, Exception):
            raise page
        if page is None:
            raise HttpError(404, url)
        return page, url

    def tool(self, name):
        def run(html):
            result = self.extractions[(name, html)]
            if isinstance(result, Exception):
                raise result
            return result
        return run

    def patch(self):
        return mock.patch.multiple(extract, http_get=self.http_get, trafilatura=self.tool("trafilatura"),
                                   defuddle=self.tool("defuddle"), require=lambda *t: None)


JINA = extract.JINA + URL
WAYBACK_API = extract.WAYBACK_API + extract.urllib.parse.quote(URL, safe="")
SNAPSHOT = "https://web.archive.org/web/2024/" + URL
SNAPSHOT_RAW = "https://web.archive.org/web/2024id_/" + URL


class TestFallbackOrder(unittest.TestCase):
    def setUp(self):
        self.post, self.spa = fixture("post.html"), fixture("spa.html")
        self.extractions = {("trafilatura", self.post): traf(), ("defuddle", self.post): defu(),
                            ("trafilatura", self.spa): Extraction("App", extractor="trafilatura"),
                            ("defuddle", self.spa): SkillError("no content")}

    def run_extract(self, pages):
        web = FakeWeb(pages, self.extractions)
        with web.patch(), mock.patch.object(extract, "log"):
            result = extract.extract(URL)
        return web, result

    def test_normal_post_uses_the_best_extractor_only(self):
        web, (best, attempts, snapshot) = self.run_extract({URL: self.post})
        self.assertEqual(best.extractor, "defuddle")
        self.assertEqual(web.calls, [URL])
        self.assertEqual([a.split(":")[0] for a in attempts], ["trafilatura", "defuddle"])
        self.assertIsNone(snapshot)
        self.assertEqual(best.html, self.post)

    def test_js_page_falls_back_to_jina(self):
        web, (best, attempts, snapshot) = self.run_extract({URL: self.spa, JINA: fixture("post.jina.txt")})
        self.assertEqual(best.extractor, "jina")
        self.assertEqual(web.headers[JINA]["User-Agent"], "tell-me")  # Jina answers 403 to browser agents
        self.assertEqual(web.calls, [URL, JINA])
        self.assertEqual(attempts, ["trafilatura: 1 words", "defuddle: failed (no content)", "jina: 846 words"])
        self.assertEqual(best.meta["title"], TITLE)

    def archived(self):
        self.extractions[("trafilatura", "archived")] = traf()
        self.extractions[("defuddle", "archived")] = SkillError("timeout")
        # the API answers http://; the raw copy (id_) has no Wayback toolbar
        return {WAYBACK_API: '{"archived_snapshots": {"closest": {"available": true, "url": "%s"}}}'
                             % SNAPSHOT.replace("https://web", "http://web"), SNAPSHOT_RAW: "archived"}

    def test_gone_page_skips_jina_and_uses_wayback(self):
        web, (best, attempts, snapshot) = self.run_extract({URL: HttpError(404, URL), **self.archived()})
        self.assertEqual(web.calls, [URL, WAYBACK_API, SNAPSHOT_RAW])
        self.assertEqual(best.extractor, "wayback+trafilatura")
        self.assertEqual(snapshot, SNAPSHOT)
        self.assertEqual([a.split(":")[0] for a in attempts],
                         ["fetch", "jina", "wayback+trafilatura", "wayback+defuddle"])
        self.assertEqual(attempts[1], "jina: skipped (the page is gone)")

    def test_unreachable_page_tries_jina_then_wayback(self):
        web, (best, _, _) = self.run_extract({URL: SkillError("could not fetch"),
                                              JINA: HttpError(451, JINA), **self.archived()})
        self.assertEqual(web.calls, [URL, JINA, WAYBACK_API, SNAPSHOT_RAW])
        self.assertEqual(best.extractor, "wayback+trafilatura")

    def test_gone_page_without_archive_fails_instead_of_saving_the_error_page(self):
        with self.assertRaisesRegex(SkillError, "is gone .HTTP 410.*wayback: no snapshot"):
            self.run_extract({URL: HttpError(410, URL), WAYBACK_API: '{"archived_snapshots": {}}'})

    def test_nothing_works_lists_every_attempt(self):
        with self.assertRaises(SkillError) as cm:
            self.run_extract({URL: SkillError("could not fetch x"), WAYBACK_API: "<html>Temporarily Offline"})
        msg = str(cm.exception)
        for part in ("fetch: could not fetch", "jina: failed", "wayback: failed (the Wayback Machine answered"):
            self.assertIn(part, msg)

    def test_short_page_keeps_the_longest_result(self):
        short = Extraction("only a few words here", extractor="jina")
        with mock.patch.object(extract, "from_jina", return_value=short):
            _, (best, attempts, _) = self.run_extract({URL: self.spa, JINA: "x", WAYBACK_API: "{}"})
        self.assertEqual(best.extractor, "jina")
        self.assertEqual(attempts[-1], "wayback: no snapshot")


if __name__ == "__main__":
    unittest.main()

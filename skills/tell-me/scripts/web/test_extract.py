#!/usr/bin/env python3
"""Unit tests for web/extract.py (offline: recorded fixtures, network and tools mocked)."""
import email.message
import json
import shlex
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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

    def test_defuddle_malformed_schema_org_is_ignored(self):
        for schema in ('[[{"headline": "x"}]]', '["str"]', '"str"'):
            ex = from_defuddle(f'{{"content": "text", "schemaOrgData": {schema}}}')
            self.assertEqual((ex.markdown, ex.meta["title"]), ("text", None), schema)
        with self.assertRaisesRegex(SkillError, "no JSON object"):
            from_defuddle("[1]")

    def test_one_crashing_extractor_keeps_the_other(self):
        attempts = []
        with mock.patch.object(extract, "trafilatura", return_value=traf()), \
                mock.patch.object(extract, "defuddle", side_effect=AttributeError("boom")):
            best = extract.extract_html("<p>x</p>", URL, attempts)
        self.assertEqual(best.extractor, "trafilatura")
        self.assertIn("defuddle: failed (boom)", attempts)

    def test_defuddle_date_as_written_is_left_to_trafilatura(self):
        ex = from_defuddle('{"content": "x", "published": "March 5, 2024"}')
        self.assertIsNone(ex.meta["published"])
        merged = pick([ex, from_trafilatura('---\ndate: 2024-03-05\n---\nx')])
        self.assertEqual(merged.meta["published"], "2024-03-05")

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
        # trafilatura flattens code into prose and keeps the "More recent articles" link list
        t, d = traf(), defu()
        self.assertIn("## More recent articles", t.markdown)
        self.assertGreater(score(d.markdown), score(t.markdown))
        self.assertEqual(pick([t, d]).extractor, "defuddle")

    def test_code_counts_as_content(self):
        prose = "one two three"
        self.assertGreater(score(prose + "\n\n```\nfour five six\n```"), score(prose))
        # a mostly-code tutorial is not "under MIN_WORDS": words and score count the same text
        tutorial = Extraction("Intro.\n\n```python\n" + "x = compute(value)\n" * 100 + "```")
        self.assertEqual(tutorial.words, 301)

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
                         "[a](https://h.com/x) ![i](https://h.com/blog/img.png) [b](https://o/y) "
                         "[c](https://h.com/blog/post#frag) [d](mailto:m@x)")


class TestNormalize(unittest.TestCase):
    def test_heading_gets_its_own_block(self):
        self.assertEqual(normalize("`cmd`\n## Next\ntext\n\n\n\nmore  "), "`cmd`\n\n## Next\n\ntext\n\nmore")
        self.assertEqual(normalize("## A\n```\nx\n```"), "## A\n\n```\nx\n```")

    def test_control_characters_dropped(self):
        self.assertEqual(normalize("a\x00b\x1bc\td"), "abc\td")

    def test_script_links_become_text(self):
        self.assertEqual(normalize("[click](javascript:alert(document.cookie)) ![i](vbscript:x) [m](mailto:a@b.c)"),
                         "click i [m](mailto:a@b.c)")

    def test_data_links_become_text(self):
        self.assertEqual(normalize("[Download](data:text/plain,<a href=x>(1)</a> more) and [b](https://b)"),
                         "Download and [b](https://b)")
        self.assertEqual(normalize("[T](data:x,unclosed ( paren\nnext line"), "T\nnext line")

    def test_fenced_code_untouched(self):
        md = "```\n# comment\n\n\n# another\n```"
        self.assertEqual(normalize(md), md)
        md = "```md\n![dot](data:image/png;base64,AA)\n```"
        self.assertEqual(normalize(md), md)

    def test_code_spans_untouched(self):
        self.assertEqual(normalize("use `[a](data:text/plain,hi)` not [b](data:x)"),
                         "use `[a](data:text/plain,hi)` not b")

    def test_linked_data_image_keeps_the_link(self):
        self.assertEqual(normalize("[![logo](data:image/png;base64,AA)](https://site.dev/home)"),
                         "[logo](https://site.dev/home)")


class TestUrls(unittest.TestCase):
    def test_raw_snapshot(self):
        self.assertEqual(raw_snapshot(SNAPSHOT), SNAPSHOT_RAW)

    def test_jina_keeps_the_app_route(self):
        with mock.patch.object(extract, "http_get", return_value=("Markdown Content:\nx", "", True)) as get:
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
        if isinstance(page, tuple):  # a redirect: (html, final URL[, permanent])
            return (*page, True)[:3]
        return page, url, True

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

    def run_extract(self, pages) -> tuple[FakeWeb, extract.Page]:
        web = FakeWeb(pages, self.extractions)
        with web.patch(), mock.patch.object(extract, "log"):
            return web, extract.extract(URL)

    def archived(self, status="200"):
        self.extractions[("trafilatura", "archived")] = traf()
        self.extractions[("defuddle", "archived")] = SkillError("timeout")
        # the API answers http://; the raw copy (id_) has no Wayback toolbar
        snap = {"available": True, "url": SNAPSHOT.replace("https://web", "http://web"), "status": status}
        return {WAYBACK_API: json.dumps({"archived_snapshots": {"closest": snap}}), SNAPSHOT_RAW: "archived"}

    def test_normal_post_uses_the_best_extractor_only(self):
        web, page = self.run_extract({URL: self.post})
        self.assertEqual(page.best.extractor, "defuddle")
        self.assertEqual(web.calls, [URL])
        self.assertEqual([a.split(":")[0] for a in page.attempts], ["trafilatura", "defuddle"])
        self.assertEqual((page.snapshot, page.gone, page.final_url), (None, 0, URL))
        self.assertEqual(page.best.html, self.post)

    def test_js_page_falls_back_to_jina(self):
        web, page = self.run_extract({URL: self.spa, JINA: fixture("post.jina.txt")})
        self.assertEqual(page.best.extractor, "jina")
        self.assertEqual(web.headers[JINA]["User-Agent"], "tell-me")  # Jina answers 403 to browser agents
        self.assertEqual(web.calls, [URL, JINA])
        self.assertEqual(page.attempts, ["trafilatura: 1 words", "defuddle: failed (no content)", "jina: 846 words"])
        self.assertEqual(page.best.meta["title"], TITLE)

    def test_gone_page_skips_jina_and_uses_wayback(self):
        web, page = self.run_extract({URL: HttpError(404, URL, "<h1>Not found</h1>"), **self.archived()})
        self.assertEqual(web.calls, [URL, WAYBACK_API, SNAPSHOT_RAW])
        self.assertEqual(page.best.extractor, "wayback+trafilatura")
        self.assertEqual((page.snapshot, page.gone), (SNAPSHOT, 404))
        self.assertEqual([a.split(":")[0] for a in page.attempts],
                         ["fetch", "jina", "wayback+trafilatura", "wayback+defuddle"])
        self.assertEqual(page.attempts[1], "jina: skipped (the page is gone)")

    def test_redirect_to_home_page_is_gone(self):
        home = "https://example.com/?p=us"
        web, page = self.run_extract({URL: (self.post, home), **self.archived()})
        self.assertEqual(web.calls, [URL, WAYBACK_API, SNAPSHOT_RAW])
        self.assertEqual((page.best.extractor, page.gone, page.final_url), ("wayback+trafilatura", 404, URL))
        self.assertIn("redirected to the home page", page.attempts[0])

    def test_consent_wall_is_not_the_article(self):
        wall = "https://consent.yahoo.com/v2/collectConsent?sessionId=1"
        web, page = self.run_extract({URL: (self.spa, wall), JINA: fixture("post.jina.txt"),
                                      WAYBACK_API: '{"archived_snapshots": {}}'})
        self.assertEqual(web.calls, [URL, WAYBACK_API, JINA])  # Jina would follow the same redirect
        self.assertEqual((page.best.extractor, page.gone, page.final_url), ("jina", 0, URL))
        self.assertIn(f"fetch: redirected to a consent or login page {wall}", page.attempts)

    def test_consent_wall_prefers_the_archive(self):
        wall = "https://a.test/login?next=/post"
        web, page = self.run_extract({URL: (self.spa, wall), **self.archived()})
        self.assertEqual(web.calls, [URL, WAYBACK_API, SNAPSHOT_RAW])
        self.assertEqual((page.best.extractor, page.snapshot, page.gone), ("wayback+trafilatura", SNAPSHOT, 0))

    def test_full_article_after_a_wall_like_redirect_is_kept(self):
        _, page = self.run_extract({URL: (self.post, "https://a.test/sso/post")})
        self.assertEqual((page.best.extractor, page.final_url), ("defuddle", "https://a.test/sso/post"))

    def test_wall(self):
        for final, wall in [("https://consent.yahoo.com/v2/collectConsent?s=1", True),
                            ("https://a.test/login?next=/post/1", True), ("https://accounts.b.test/x", True),
                            ("https://a.test/post/1", False), ("https://a.test/blog/logins-explained", False),
                            ("https://a.test/login-flows-explained/", False), ("https://a.test/consent-management", False),
                            ("https://login.gov/help/", False), ("https://a.test/auth/", True)]:
            self.assertEqual(extract.is_wall("https://a.test/post/1", final), wall, final)

    def test_temporary_redirect_is_not_permanent(self):
        _, page = self.run_extract({URL: (self.post, URL + "?v=2", False)})
        self.assertFalse(page.permanent)
        _, page = self.run_extract({URL: self.post})
        self.assertTrue(page.permanent)

    def test_private_address_never_sent_to_third_parties(self):
        local = "http://localhost:8080/notes"
        web = FakeWeb({local: self.spa}, self.extractions)
        with web.patch(), mock.patch.object(extract, "log"):
            page = extract.extract(local)
        self.assertEqual(web.calls, [local])
        self.assertIn("skipped (a private address", page.attempts[-1])
        for url, private in [("http://10.0.0.5/x", True), ("http://intranet/x", True), ("http://nas.local/", True),
                             ("http://[::1]/", True), ("https://8.8.8.8/", False), ("https://a.test/", False)]:
            self.assertEqual(extract.is_private(url), private, url)

    def test_short_real_page_behind_an_error_is_kept(self):
        short = Extraction("A short note " + "with real words " * 20, extractor="jina")
        with mock.patch.object(extract, "from_jina", return_value=short):
            _, page = self.run_extract({URL: HttpError(403, URL, "<p>x</p>"), JINA: "x", WAYBACK_API: "{}"})
        self.assertEqual(page.best.extractor, "jina")

    def test_challenge_page_is_not_saved_as_the_article(self):
        short = Extraction("Just a moment... checking your browser", extractor="jina")
        with mock.patch.object(extract, "from_jina", return_value=short):
            with self.assertRaisesRegex(SkillError, "answered HTTP 403 and no fallback got the article"):
                self.run_extract({URL: HttpError(403, URL, "<p>Just a moment</p>"), JINA: "x", WAYBACK_API: "{}"})

    def test_soft_404(self):
        for url, final, soft in [("https://a.test/post/1", "https://b.test/", True),
                                 ("https://t.co/abc123", "https://b.test/", False),
                                 ("https://a.test/en", "https://a.test/", False),
                                 ("https://a.test/old.html", "https://a.test/", True),
                                 ("https://www.a.test/2024/post", "https://a.test/?p=12", False),
                                 ("https://a.test/post/1", "https://a.test", True),
                                 ("https://a.test/index.html", "https://a.test/", False),
                                 ("https://a.test/", "https://a.test/", False),
                                 ("https://a.test/post/1", "https://a.test/?id=1", False),
                                 ("https://a.test/post/1", "https://a.test/new/post", False)]:
            self.assertEqual(extract.is_soft_404(url, final), soft, (url, final))

    def test_app_shell_404_still_tries_jina(self):
        # a single-page app on GitHub Pages answers 404 (its 404.html) for every deep link
        web, page = self.run_extract({URL: HttpError(404, URL, self.spa), JINA: fixture("post.jina.txt")})
        self.assertEqual(web.calls, [URL, JINA])
        self.assertEqual((page.best.extractor, page.gone), ("jina", 0))

    def test_cut_off_live_page_uses_the_archive_but_is_not_gone(self):
        short = Extraction("only a teaser", extractor="jina")
        with mock.patch.object(extract, "from_jina", return_value=short):
            _, page = self.run_extract({URL: self.spa, JINA: "x", **self.archived()})
        self.assertEqual((page.best.extractor, page.snapshot, page.gone), ("wayback+trafilatura", SNAPSHOT, 0))

    def test_unreachable_page_tries_jina_then_wayback(self):
        web, page = self.run_extract({URL: SkillError("could not fetch"), JINA: HttpError(451, JINA),
                                      **self.archived()})
        self.assertEqual(web.calls, [URL, JINA, WAYBACK_API, SNAPSHOT_RAW])
        self.assertEqual(page.best.extractor, "wayback+trafilatura")

    def test_archived_error_page_is_not_a_copy(self):
        with self.assertRaisesRegex(SkillError, "is gone .HTTP 404.*wayback: no snapshot"):
            self.run_extract({URL: HttpError(404, URL), **self.archived(status="404")})

    def test_gone_page_without_archive_fails_instead_of_saving_the_error_page(self):
        with self.assertRaisesRegex(SkillError, "is gone .HTTP 410.*wayback: no snapshot"):
            self.run_extract({URL: HttpError(410, URL), WAYBACK_API: '{"archived_snapshots": {}}'})

    def test_document_url_is_refused_at_once(self):
        with self.assertRaisesRegex(extract.NotAPage, "application/pdf"):
            self.run_extract({URL: extract.NotAPage(f"{URL} is a application/pdf document")})

    def test_nothing_works_lists_every_attempt(self):
        with self.assertRaises(SkillError) as cm:
            self.run_extract({URL: SkillError("could not fetch x"), WAYBACK_API: "<html>Temporarily Offline"})
        msg = str(cm.exception)
        for part in ("fetch: could not fetch", "jina: failed", "wayback: failed (the Wayback Machine answered"):
            self.assertIn(part, msg)

    def test_short_page_keeps_the_longest_result(self):
        short = Extraction("only a few words here", extractor="jina")
        with mock.patch.object(extract, "from_jina", return_value=short):
            _, page = self.run_extract({URL: self.spa, JINA: "x", WAYBACK_API: "{}"})
        self.assertEqual(page.best.extractor, "jina")
        self.assertEqual(page.attempts[-1], "wayback: no snapshot")


class TestHttpGet(unittest.TestCase):
    def response(self, body: bytes, ctype: str):
        r = mock.MagicMock()
        r.__enter__.return_value = r
        r.headers = email.message.Message()
        r.headers["Content-Type"] = ctype
        r.read.side_effect = lambda n=-1: body[:n] if n >= 0 else body
        r.geturl.return_value = URL
        return r

    def test_charset_from_meta_when_the_header_has_none(self):
        page = '<meta charset="iso-8859-1"><p>Café</p>'.encode("latin-1")
        with mock.patch.object(extract, "open_url", return_value=self.response(page, "text/html")):
            self.assertIn("Café", extract.http_get(URL)[0])

    def test_undeclared_legacy_charset(self):
        page = "<title>XTM’s HOMEPAGE</title>".encode("cp1252")
        with mock.patch.object(extract, "open_url", return_value=self.response(page, "text/html")):
            self.assertIn("XTM’s", extract.http_get(URL)[0])

    def test_pdf_is_not_a_page(self):
        with mock.patch.object(extract, "open_url", return_value=self.response(b"%PDF-1.7", "application/pdf")):
            with self.assertRaisesRegex(extract.NotAPage, "application/pdf document"):
                extract.http_get(URL)

    def test_the_file_command_in_the_message_quotes_the_url(self):
        url = "https://x.org/it's here.pdf?a=1&b=2"
        with mock.patch.object(extract, "open_url", return_value=self.response(b"%PDF-1.7", "application/pdf")):
            with self.assertRaises(extract.NotAPage) as caught:
                extract.http_get(url)
        self.assertIn(f"scripts/file/prepare.py {shlex.quote(url)})", str(caught.exception))


class Redirects(BaseHTTPRequestHandler):
    """/p301 -> /p308 -> /page (both permanent); /temp -> /page (302)."""
    ROUTES = {"/p301": (301, "/p308"), "/p308": (308, "/page"), "/temp": (302, "/page")}

    def do_GET(self):
        if self.path in self.ROUTES:
            code, to = self.ROUTES[self.path]
            self.send_response(code)
            self.send_header("Location", to)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"<p>page</p>")

    def log_message(self, *args):
        pass


class TestRedirectLog(unittest.TestCase):
    def test_permanence_of_the_redirect_chain(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Redirects)  # local only: no network
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_port}"
        self.assertEqual(extract.http_get(base + "/p301"), ("<p>page</p>", base + "/page", True))
        self.assertEqual(extract.http_get(base + "/temp")[1:], (base + "/page", False))
        self.assertEqual(extract.http_get(base + "/page")[1:], (base + "/page", True))


if __name__ == "__main__":
    unittest.main()

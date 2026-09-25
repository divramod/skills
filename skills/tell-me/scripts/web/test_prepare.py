#!/usr/bin/env python3
"""Unit tests for web/prepare.py (offline: extract() is mocked, the library is a temp folder)."""
import io
import json
import os
import re
import sys
import tempfile
import unittest
import urllib.parse
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

import prepare
from _common import CONTRACT_KEYS, ENVELOPE_KEYS, SkillError, read_json
from extract import Extraction, Page, from_defuddle
from prepare import anchor, block_words, blocks, fragment, heading_ids, kind, page_url

FIXTURES = Path(__file__).resolve().parent / "fixtures"
URL = "https://simonwillison.net/2024/Dec/19/one-shot-python-tools/"


def fragment_text(link: str) -> str:
    return urllib.parse.unquote(link.split("#:~:text=", 1)[1])


class TestFragment(unittest.TestCase):
    def test_encoding(self):
        # dashes, commas, ampersands and spaces would break the fragment syntax
        self.assertEqual(fragment(["one-shot,", "A&B", "ümlaut"]), "#:~:text=one%2Dshot%2C%20A%26B%20%C3%BCmlaut")

    def test_block_words_as_the_browser_shows_them(self):
        self.assertEqual(block_words("- **Bold** and _em_ in [a link](https://x) `snake_case` ![img](i.png)"),
                         ["Bold", "and", "em", "in", "a", "link", "snake_case"])
        self.assertEqual(block_words("> > nested &amp; quoted"), ["nested", "&", "quoted"])
        self.assertEqual(block_words("1. first item"), ["first", "item"])


class TestBlocks(unittest.TestCase):
    def test_fenced_code_with_blank_lines_stays_whole(self):
        md = "para one\n\n```\ncode\n\nmore code\n```\n\npara two"
        self.assertEqual(blocks(md), ["para one", "```\ncode\n\nmore code\n```", "para two"])

    def test_kinds(self):
        self.assertEqual([kind(b) for b in ("# H", "```x```", "    indented", "| a | b |", "---", "![i](u)",
                                            "text", "- item", "> quote")],
                         ["heading", "code", "code", "other", "other", "other", "text", "text", "text"])


class TestAnchor(unittest.TestCase):
    def test_every_text_block_numbered_in_order(self):
        out = anchor("# Title\n\nFirst para here.\n\n```\ncode\n```\n\n- a list item\n- second\n\n> a quote", URL)
        self.assertEqual(out.split("\n\n"), [
            "# Title",
            f"[¶1]({URL}#:~:text=First%20para%20here.) First para here.",
            "```\ncode\n```",
            f"- [¶2]({URL}#:~:text=a%20list%20item) a list item\n- second",
            f"> [¶3]({URL}#:~:text=a%20quote) a quote",
        ])

    def test_fragment_stays_in_the_first_block_element(self):
        # a text fragment cannot match across two <li>s or two <p>s of a quote
        out = anchor("> quote one\n> wraps\n>\n> para two\n\n1. x y\n2. z", URL)
        self.assertEqual(fragment_text(out.split(")")[0]), "quote one wraps")
        self.assertIn("#:~:text=x%20y)", out)

    def test_app_route_is_kept(self):
        out = anchor("## Setup\n\nsome text", "https://docsify.js.org/#/quickstart", {"setup": "setup"})
        self.assertEqual(out, "## Setup\n\n[¶1](https://docsify.js.org/#/quickstart:~:text=some%20text) some text")

    def test_fragment_grows_until_its_first_match_is_its_own_paragraph(self):
        same = "one two three four five six seven"
        out = anchor(f"{same} A\n\n{same} B\n\nother text", URL)
        links = [line.split(")", 1)[0] for line in out.split("\n\n")]
        self.assertEqual(fragment_text(links[0]), "one two three four five")  # its first match is itself
        self.assertEqual(fragment_text(links[1]), same + " B")
        self.assertEqual(fragment_text(links[2]), "other text")

    def test_fragment_uniqueness_is_page_wide_and_case_insensitive(self):
        # browsers take the first match anywhere, ignoring case: here, inside paragraph 1
        out = anchor("We said that in this post we will cover a lot.\n\nIn this post we will cover X today.", URL)
        self.assertEqual(fragment_text(re.findall(r"\[¶2\]\(([^)]+)\)", out)[0]),
                         "In this post we will cover X")
        # ... or in the title above the article
        out = anchor("Why Rust is fast and safe for us", URL, preamble="Why Rust is fast and safe")
        self.assertEqual(fragment_text(out.split(")")[0]), "Why Rust is fast and safe for")

    def test_backslash_escapes_are_the_characters_the_page_shows(self):
        # defuddle (turndown) escapes markdown characters: snake\_case, \*x\*, 1\.
        self.assertEqual(block_words("Use the snake\\_case helper \\*carefully\\* in step 1\\. and \\[x\\]"),
                         ["Use", "the", "snake_case", "helper", "*carefully*", "in", "step", "1.", "and", "[x]"])
        self.assertEqual(block_words("*real* _emphasis_"), ["real", "emphasis"])

    def test_heading_ids_are_encoded(self):
        out = anchor("## Evil", URL, {"evil": "a b) [x](javascript:alert(1)"})
        self.assertEqual(out, f"## Evil [#]({URL}#a%20b%29%20%5Bx%5D%28javascript:alert%281%29)")

    def test_url_fragment_and_ids(self):
        out = anchor("## Custom *instructions*\n\n## No id\n\ntext", URL + "#old",
                     {"custom instructions": "custom-instructions"})
        self.assertEqual(out.split("\n\n")[:2],
                         [f"## Custom *instructions* [#]({URL}#custom-instructions)", "## No id"])
        self.assertIn(f"({URL}#:~:text=text)", out)

    def test_recorded_post(self):
        md = from_defuddle((FIXTURES / "post.defuddle.json").read_text()).markdown
        ids = heading_ids((FIXTURES / "post.html").read_text())
        out = anchor(md, URL, ids)
        self.assertIn(f"#### Custom instructions [#]({URL}#custom-instructions)", out)
        numbers = [int(n) for n in re.findall(r"\[¶(\d+)\]", out)]
        self.assertEqual(numbers, list(range(1, len(numbers) + 1)))
        texts = [fragment_text(link) for link in re.findall(r"\[¶\d+\]\(([^)]+)\)", out)]
        self.assertEqual(len(texts), len(set(texts)), "every fragment is unique")
        self.assertIn("I’ve written a lot about", texts[0])


class TestHeadingIds(unittest.TestCase):
    def test_id_on_heading_or_inner_anchor(self):
        page = ('<h2 id="a">Alpha &amp; Beta</h2><h3><a name="b"></a>Gamma</h3><h4>No id</h4>'
                '<p id="p">not a heading</p>')
        self.assertEqual(heading_ids(page), {"alpha beta": "a", "gamma": "b"})

    def test_docs_generator_permalinks_ignored(self):
        # Sphinx/MkDocs put a ¶ permalink in the heading, Docusaurus a zero-width space
        page = '<h2 id="setup">Setup<a class="headerlink" href="#setup">¶</a></h2><h2 id="run">Run\u200b</h2>'
        ids = heading_ids(page)
        self.assertEqual(anchor("## Setup\n\n## Run", URL, ids),
                         f"## Setup [#]({URL}#setup)\n\n## Run [#]({URL}#run)")

    def test_sphinx_ids_from_permalink_or_section(self):
        # docs.python.org: the id is on the <section>, the heading only links to it
        page = ('<section id="intro">\n<h1>Intro<a class="headerlink" href="#intro">¶</a></h1>\n<p>x</p>'
                '<section id="use-it">\n<h2>Use it</h2></section>'
                '<section id="s"><p>text first</p><h2>Late</h2></section>'
                '<h2>Linked <a href="https://x.test/#y">y</a></h2>')
        self.assertEqual(heading_ids(page), {"intro": "intro", "use it": "use-it"})

    def test_other_in_heading_links_are_no_permalink(self):
        page = ('<h2><a href="#toc">Install</a></h2><h2>Run<sup><a href="#fn1">1</a></sup></h2>'
                '<h2><a class="anchor" href="#usage">Usage</a></h2>')
        self.assertEqual(heading_ids(page), {"usage": "usage"})

    def test_extracted_permalinks_replaced(self):
        # trafilatura keeps Sphinx's ¶ link but drops the path from its URL
        md = "# Intro[¶](https://docs.python.org#intro)\n\n## Use it [](#use-it)\n\n## See [docs](https://d.test)"
        self.assertEqual(anchor(md, URL, {"intro": "intro"}).split("\n\n"),
                         [f"# Intro [#]({URL}#intro)", "## Use it", "## See [docs](https://d.test)"])


class TestPageUrl(unittest.TestCase):
    def test_tracking_and_fragment_dropped(self):
        self.assertEqual(page_url("https://www.Ex.com/a?utm_source=x&id=3&fbclid=y#top"), "https://www.Ex.com/a?id=3")
        self.assertEqual(page_url(URL), URL)
        self.assertEqual(page_url("https://docsify.js.org/?utm_medium=x#/quickstart"), "https://docsify.js.org/#/quickstart")


class TestMain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        env = mock.patch.dict(os.environ, {"TELL_ME_ROOT": self.tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(self.tmp.cleanup)
        post = from_defuddle((FIXTURES / "post.defuddle.json").read_text())
        post.meta |= {"published": "2024-12-19"}
        post.html = (FIXTURES / "post.html").read_text()
        self.post = post
        self.attempts = ["trafilatura: 852 words", "defuddle: 843 words"]

    def page(self, best=None, **kw):
        """extract() as a mock: the fetched URL is the final URL unless given."""
        return lambda url: Page(best or self.post, self.attempts, kw.pop("final_url", url), **kw)

    def run_main(self, *args, page=None):
        out = io.StringIO()
        with mock.patch.object(prepare, "extract", side_effect=page or self.page()) as ex, \
                mock.patch.object(prepare, "log"), redirect_stdout(out):
            self.assertEqual(prepare.main(list(args)), 0)
        return json.loads(out.getvalue()), ex

    def test_prepares_folder_content_and_contract(self):
        env, ex = self.run_main(URL + "?utm_source=rss#frag")
        ex.assert_called_once_with(URL)
        folder = self.root / "articles" / "simon-willisons-weblog" / (
            "building-python-tools-with-a-one-shot-prompt-using-uv-run-and-claude-projects")
        self.assertEqual(env["dir"], str(folder))
        self.assertTrue(set(ENVELOPE_KEYS) <= set(env))
        self.assertEqual((env["source"], env["kind"], env["extractor"], env["reused"]), ("web", "page", "defuddle", False))
        meta = read_json(folder / "metadata.json")
        self.assertTrue(set(CONTRACT_KEYS) <= set(meta))
        self.assertEqual((meta["id"], meta["url"], meta["published"], meta["site"]),
                         (URL, URL, "2024-12-19", "Simon Willison’s Weblog"))
        self.assertEqual(meta["extras"]["language"], "en-gb")
        content = (folder / "content.md").read_text()
        self.assertTrue(content.startswith("# Building Python tools"))
        self.assertIn("- extractor: defuddle (843 words)", content)
        self.assertIn(f"[¶1]({URL}#:~:text=", content)
        self.assertNotIn("utm_source", content)

    def test_rerun_reuses_the_folder(self):
        first, _ = self.run_main(URL)
        second, ex = self.run_main("http://www.simonwillison.net/2024/Dec/19/one-shot-python-tools/")
        ex.assert_not_called()
        self.assertEqual((second["dir"], second["reused"]), (first["dir"], True))

    def test_refresh_refetches_into_the_same_folder(self):
        first, _ = self.run_main(URL)
        prepared_at = read_json(Path(first["dir"]) / "metadata.json")["prepared_at"]
        second, ex = self.run_main(URL, "--refresh")
        ex.assert_called_once()
        self.assertEqual((second["dir"], second["reused"]), (first["dir"], True))
        self.assertEqual(read_json(Path(first["dir"]) / "metadata.json")["prepared_at"], prepared_at)

    def test_same_title_other_page_gets_its_own_folder(self):
        first, _ = self.run_main(URL)
        second, _ = self.run_main(URL + "copy/")
        self.assertNotEqual(first["dir"], second["dir"])
        self.assertTrue(Path(second["dir"]).name.startswith(Path(first["dir"]).name + "-"))

    def test_wayback_text_anchors_to_the_snapshot(self):
        snap = "https://web.archive.org/web/2024/" + URL
        self.post.extractor = "wayback+defuddle"
        env, _ = self.run_main(URL, page=self.page(snapshot=snap, gone=404))
        content = Path(env["content_file"]).read_text()
        self.assertIn(f"[¶1]({snap}#:~:text=", content)
        self.assertIn(f"- archived copy: {snap}", content)
        self.assertEqual((env["snapshot"], env["gone"]), (snap, 404))

    def test_redirect_and_canonical_url_dedupe(self):
        short = "https://t.co/abc123"
        self.post.meta["url"] = URL + "?ref=feed"  # the page's canonical/og:url
        first, _ = self.run_main(short, page=self.page(final_url=URL + "?utm_source=t"))
        meta = read_json(Path(first["dir"]) / "metadata.json")
        self.assertEqual((meta["id"], meta["url"]), (URL + "?ref=feed", URL + "?ref=feed"))
        self.assertEqual(meta["extras"]["aliases"], [short, URL])
        # the short link again: no fetch; the plain URL: fetched, found as an alias, reused
        again, ex = self.run_main(short)
        ex.assert_not_called()
        plain, _ = self.run_main(URL)
        self.assertEqual({again["dir"], plain["dir"]}, {first["dir"]})
        self.assertTrue(plain["reused"])

    def test_query_variants_share_the_canonical_folder(self):
        self.post.meta["url"] = URL
        first, _ = self.run_main(URL + "?ref=a")
        self.post.meta["title"] = "Retitled"  # a second folder would show up as a duplicate
        second, _ = self.run_main(URL + "?ref=b")
        self.assertEqual((second["dir"], second["reused"]), (first["dir"], True))
        aliases = read_json(Path(first["dir"]) / "metadata.json")["extras"]["aliases"]
        self.assertEqual(aliases, [URL + "?ref=a", URL + "?ref=b"])

    def test_temporary_redirect_is_no_alias(self):
        latest = "https://example.com/latest"
        first, _ = self.run_main(latest, page=self.page(final_url=URL, permanent=False))
        self.assertNotIn(latest, read_json(Path(first["dir"]) / "metadata.json")["extras"].get("aliases", []))
        _, ex = self.run_main(latest, page=self.page(final_url=URL + "next/", permanent=False))
        ex.assert_called_once()  # fetched again: /latest may be another post now

    def test_off_site_or_other_path_canonical_is_ignored(self):
        self.assertEqual(prepare.canonical_url(URL, URL, "https://other.site/p"), URL)
        self.assertEqual(prepare.canonical_url(URL, URL, "https://simonwillison.net/"), URL)
        self.assertEqual(prepare.canonical_url(URL, URL, "https://simonwillison.net/2024/"), URL)
        self.assertEqual(prepare.canonical_url(URL, URL + "?page=2", URL.rstrip("/")), URL.rstrip("/"))
        self.assertEqual(prepare.canonical_url(URL, URL + "?utm_source=x", None), URL)
        self.assertEqual(prepare.canonical_url("https://d.io/#/start", "https://d.io/", "https://d.io/"),
                         "https://d.io/#/start")

    def test_untitled_page_falls_back_to_the_path(self):
        env, _ = self.run_main("https://example.com/notes/my-page", page=self.page(Extraction("word " * 300)))
        self.assertEqual((env["title"], Path(env["dir"]).parent.name), ("my-page", "example-com"))

    def test_other_source_is_refused(self):
        with self.assertRaisesRegex(SkillError, "is a github input"):
            prepare.main(["https://github.com/astral-sh/uv"])


if __name__ == "__main__":
    unittest.main()

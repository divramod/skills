#!/usr/bin/env python3
"""Unit tests for render_html.py (offline)."""
import json
import tempfile
import unittest
from pathlib import Path

from render_html import build, inline, markdown, split_frontmatter
from save_summary import render

META = {"id": "abc", "title": "T <x>", "channel": "Chan", "webpage_url": "https://www.youtube.com/watch?v=abc",
        "upload_date": "20260924", "duration": 729, "platform": "youtube", "transcript_source": "whisper"}


class TestInline(unittest.TestCase):
    def test_emphasis_code_and_escaping(self):
        self.assertEqual(inline("**b** *i* `a<b>` <x> & y"), "<strong>b</strong> <em>i</em> <code>a&lt;b&gt;</code> &lt;x&gt; &amp; y")

    def test_timestamp_links_get_seek_data(self):
        out = inline("([00:44](https://www.youtube.com/watch?v=abc&t=44s))")
        self.assertIn('target="_blank"', out)  # the page script seeks the player instead when there is one
        self.assertIn('class="ts" data-t="44"', out)
        self.assertIn('href="https://www.youtube.com/watch?v=abc&amp;t=44s"', out)

    def test_plain_link_and_autolink(self):
        self.assertEqual(inline("[a](https://x.io/p_q)"), '<a href="https://x.io/p_q" target="_blank" rel="noopener">a</a>')
        self.assertIn('<a href="https://typesafe.ai" target="_blank" rel="noopener">https://typesafe.ai</a>.', inline("see https://typesafe.ai."))

    def test_script_urls_are_neutralized(self):
        for url in ("javascript:alert(1)", "JavaScript:x", "vbscript:x", "data:text/html,<script>x</script>"):
            with self.subTest(url):
                self.assertIn('href="#"', inline(f"[x]({url.replace(' ', '')})"))
        self.assertIn('src="data:image/png;base64,AAA"', inline("![i](data:image/png;base64,AAA)"))
        self.assertIn('href="https://ok.dev"', inline("[x](https://ok.dev)"))

    def test_link_with_parentheses(self):
        self.assertIn('href="https://en.wikipedia.org/wiki/LoRA_(machine_learning)" target="_blank" rel="noopener">LoRA</a>)',
                      inline("[LoRA](https://en.wikipedia.org/wiki/LoRA_(machine_learning)))"))

    def test_relative_image_gets_base(self):
        self.assertIn('src="frames/001.jpg"', inline("![00:05](001.jpg)", base="frames/"))

    def test_underscores_inside_words_are_not_emphasis(self):
        self.assertEqual(inline("video_file and snake_case"), "video_file and snake_case")


class TestUntrustedText(unittest.TestCase):
    def test_stray_nul_does_not_hang(self):
        self.assertEqual(inline("a\x00b \x001\x00 `c`"), "ab 1 <code>c</code>")


class TestBlocks(unittest.TestCase):
    def test_nested_lists(self):
        html = markdown("- a\n  - b\n- c\n\n1. x\n2. y")
        self.assertEqual(html, "<ul><li>a<ul><li>b</li></ul></li><li>c</li></ul>\n<ol><li>x</li><li>y</li></ol>")

    def test_table_heading_quote_code(self):
        html = markdown("## H\n\n| # | V |\n|---|---|\n| 1 | **x** |\n\n> q\n\n```\n<a>\n```\n\npara\nline")
        self.assertIn("<h2>H</h2>", html)
        self.assertIn("<th>#</th><th>V</th>", html)
        self.assertIn("<td><strong>x</strong></td>", html)
        self.assertIn("<blockquote><p>q</p></blockquote>", html)
        self.assertIn("<pre><code>&lt;a&gt;</code></pre>", html)
        self.assertIn("<p>para line</p>", html)

    def test_frontmatter(self):
        meta, rest = split_frontmatter('---\ntitle: "Say \\"hi\\""\nvideos: 2\n---\n\nbody')
        self.assertEqual(meta, {"title": 'Say "hi"', "videos": "2"})
        self.assertEqual(rest, "\nbody")


class TestPage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, meta, body="**TL;DR:** ok\n\n- p ([00:44](https://www.youtube.com/watch?v=abc&t=44s))"):
        (self.dir / "metadata.json").write_text(json.dumps(meta))
        (self.dir / "summary.md").write_text(render(meta, body, "summary", "en", "2026-09-25", "claude-code 2.1", "m1"))

    def test_page_has_summary_without_duplicate_header(self):
        self.write(META)
        page = build(self.dir)
        self.assertIn("<title>T &lt;x&gt;</title>", page)
        self.assertEqual(page.count("<h1>"), 1)
        self.assertNotIn("https://www.youtube.com/watch?v=abc</p>", page.split("<article>")[1])
        self.assertIn("<p><strong>TL;DR:</strong> ok</p>", page)
        self.assertIn("<li>agent: claude-code 2.1</li>", page)
        self.assertNotIn("<video", page)

    def test_video_only_when_download_finished(self):
        self.write(META | {"video_file": "video.mkv"})
        (self.dir / "video.mkv").write_bytes(b"")
        (self.dir / ".video-download.json").write_text("{}")
        self.assertNotIn("<video", build(self.dir))
        (self.dir / ".video-download.json").unlink()
        self.assertIn('<video controls preload="metadata" src="video.mkv">', build(self.dir))

    def test_content_section(self):
        self.write(META)
        (self.dir / "content.md").write_text("# T\n\n## Transcript\n\n[[00:44](https://www.youtube.com/watch?v=abc&t=44s)] x")
        self.assertIn('<details class="content"><summary>Transcript</summary>', build(self.dir))

    def test_other_sources_have_no_player(self):
        self.write({"source": "web", "id": "u", "title": "Post", "url": "https://a.b/post", "author": "Ann",
                    "content_file": "content.md"})
        (self.dir / "content.md").write_text("# Post\n\n[¶1](https://a.b/post#:~:text=Hello) Hello")
        page = build(self.dir)
        self.assertNotIn('class="player"', page)
        self.assertIn('<details class="content"><summary>Article</summary>', page)
        self.assertIn('href="https://a.b/post"', page)

    def test_body_starting_like_info_line_is_kept_without_header_info(self):
        meta = {"id": "abc", "title": "T"}
        self.write(meta, body="first line\n\nsecond")
        self.assertIn("<p>first line</p>", build(self.dir))


class TestPageScripts(unittest.TestCase):
    """The page JS lives in Python strings; a stray escape there breaks the whole page."""

    def test_scripts_parse(self):
        import shutil
        import subprocess
        from library import SIDEBAR_JS
        from render_html import JS
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        for name, src in (("page", JS), ("sidebar", SIDEBAR_JS)):
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
                f.write(src)
            p = subprocess.run([node, "--check", f.name], capture_output=True, text=True)
            Path(f.name).unlink()
            self.assertEqual(p.returncode, 0, f"{name} script: {p.stderr}")


if __name__ == "__main__":
    unittest.main()

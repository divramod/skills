#!/usr/bin/env python3
"""Unit tests for file/convert.py (offline: markitdown, pdftotext and pandoc answer recorded output)."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.append(str(HERE.parent / "shared"))

import convert  # noqa: E402
from _common import MissingTool, SkillError  # noqa: E402

FIXTURES = HERE / "fixtures"
PDF = FIXTURES / "three-pages.pdf"
LAYOUT = "three-pages.bbox-layout.html"  # pdftotext -enc UTF-8 -bbox-layout three-pages.pdf -


def recorded(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def tools(*present: str):
    """shutil.which answering only for `present`."""
    return mock.patch.object(convert.shutil, "which", side_effect=lambda t: f"/bin/{t}" if t in present else None)


def runner(answers: dict):
    """convert.run answering by the command's tool (markitdown, layout = pdftotext -bbox-layout, bbox =
    pdftotext -bbox, pdfinfo, pandoc, textutil); an Exception answer is raised. `calls` records the tools asked."""
    calls: list[str] = []

    def run(cmd):
        tool = "markitdown" if cmd[0] == "uvx" else cmd[0]
        key = "layout" if "-bbox-layout" in cmd else "bbox" if "-bbox" in cmd else tool
        calls.append(key)
        answer = answers.get(key)
        if isinstance(answer, Exception):
            raise answer
        if answer is None:
            raise SkillError(f"{key}: no answer recorded")
        return answer
    return mock.patch.object(convert, "run", side_effect=run), calls


class TestCleanUp(unittest.TestCase):
    def test_paragraphs_hyphens_lists_and_stamps(self):
        page = "3\n2\n0\n2\n\ng\nu\nA\n\nThe second page\nholds the method, it is pur-\nposeful.\n\n- one\n- two\n"
        self.assertEqual(convert.clean_pdf_page(page),
                         "The second page holds the method, it is purposeful.\n\n- one\n- two")

    def test_short_lines_that_are_not_a_stamp_stay(self):
        self.assertEqual(convert.clean_pdf_page("Table\n1\n2\nend"), "Table 1 2 end")

    def test_a_column_of_numbers_is_no_stamp(self):
        self.assertEqual(convert.clean_pdf_page("Scores\n\n1\n2\n3\n4\n5"), "Scores\n\n1 2 3 4 5")

    def test_compounds_keep_their_hyphen_broken_words_join(self):
        page = ("We read left-to-\nright and pre-\ntrain a task-\nspecific model with self-\nattention; the "
                "hyphen-\nated word joins, BERT-\nBASE too.\n\nEvery task needs a specific head.")
        self.assertEqual(convert.clean_pdf_page(page).split("\n\n")[0],
                         "We read left-to-right and pre-train a task-specific model with self-attention; the "
                         "hyphenated word joins, BERT-BASE too.")

    def test_the_documents_own_spelling_decides(self):
        vocab = convert.vocabulary("the pretrained model\nwith a fine-tuning step")
        self.assertEqual(convert.clean_pdf_page("a pre-\ntrained model", vocab), "a pretrained model")
        self.assertEqual(convert.clean_pdf_page("a fine-\ntuning step", vocab), "a fine-tuning step")
        self.assertNotIn("pre", convert.vocabulary("a pre-\ntrained model"))  # the halves of a broken word

    def test_numbers_that_are_no_list_items(self):
        self.assertEqual(convert.clean_pdf_page("as shown in\n2018. The model\n1. first\n2) second"),
                         "as shown in 2018. The model\n1. first\n2) second")

    def test_urls_broken_at_a_line_end(self):
        self.assertEqual(convert.clean_pdf_page("code at https://github.com/google-research/\nbert and "
                                                "https://blog.\nopenai.com/language-unsupervised. See\n"
                                                "https://x.org/a-\nlong-path. Done."),
                         "code at https://github.com/google-research/bert and "
                         "https://blog.openai.com/language-unsupervised. See https://x.org/a-long-path. Done.")

    def test_a_paragraph_cut_by_a_column_break_and_section_numbers(self):
        self.assertEqual(convert.clean_pdf_page("2.1\n\nRelated Work\n\nmodels of this kind are, as the "
                                                "column before says, often\n\ntrained on text.\n\n3\n\nIt is long "
                                                "enough to be a paragraph and not a heading, so it stays."),
                         "2.1 Related Work\n\nmodels of this kind are, as the column before says, often trained on "
                         "text.\n\n3\n\nIt is long enough to be a paragraph and not a heading, so it stays.")

    def test_split_pages(self):
        self.assertEqual(convert.split_pages("a\n\fb\n\fc\n\f"), ["a", "b", "c"])

    def test_layout_pages(self):
        def line(x0, y0, x1, y1, *ws):
            return (f'<line xMin="{x0}" yMin="{y0}" xMax="{x1}" yMax="{y1}">'
                    + "".join(f'<word xMin="{x0}" yMin="{y0}" xMax="{x1}" yMax="{y1}">{w}</word>' for w in ws)
                    + "</line>")
        page = ('<page width="612" height="792"><flow><block>'
                + line(18, 200, 36, 600, "arXiv:1810.04805v2", "[cs.CL]")  # rotated in the margin
                + '</block></flow><flow><block>'
                + line(84, 100, 290, 110, "There", "are", "two", "strate-")
                + line(72, 113, 290, 123, "gies.", "It", "ends", "here.")
                + line(84, 126, 290, 136, "A", "new", "paragraph", "&amp;")
                + line(72, 139, 200, 149, "it", "ends.")
                + '</block></flow></page><page width="612" height="792">\n</page>')
        self.assertEqual(convert.layout_pages(page),
                         ["There are two strate-\ngies. It ends here.\n\nA new paragraph &\nit ends.", ""])
        pages = convert.layout_pages(recorded(LAYOUT))
        self.assertEqual(len(pages), 3)
        self.assertIn("It is short on pur-\npose and has a hyphenated word.", pages[1])  # hyphens as printed

    def test_pptx_slides(self):
        self.assertEqual(convert.pptx_slides("<!-- Slide number: 2 -->\n# Goals"), "## Slide 2\n# Goals")


class TestReadText(unittest.TestCase):
    def read(self, data: bytes) -> str:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(data)
        self.addCleanup(Path(f.name).unlink)
        return convert.read_text(Path(f.name))

    def test_encodings(self):
        text = "Café naïve – “quoted” résumé"
        self.assertEqual(self.read(text.encode("utf-8")), text)
        self.assertEqual(self.read(b"\xef\xbb\xbf" + text.encode("utf-8")), text)
        self.assertEqual(self.read(text.encode("utf-16")), text)  # with its BOM
        self.assertEqual(self.read(text.encode("cp1252")), text)
        self.assertEqual(self.read("Größe".encode("latin-1")), "Größe")
        self.assertEqual(self.read(b"\x81\xe9"), "\x81é")  # a byte cp1252 leaves undefined: Latin-1


class TestProperties(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(convert.iso_date("D:20240410231143+02'00'"), "2024-04-10")
        self.assertEqual(convert.iso_date("Wed Apr 10 23:11:43 2024 CEST"), "2024-04-10")
        self.assertEqual(convert.iso_date("2026-09-25T14:43:52Z"), "2026-09-25")
        self.assertIsNone(convert.iso_date("soon"))

    def test_office_and_epub(self):
        self.assertEqual(convert.office_props(FIXTURES / "plan.docx"),
                         {"title": "Quarterly Plan", "author": "Jane Roe", "published": "2026-09-25"})
        self.assertEqual(convert.epub_props(FIXTURES / "plan.epub")["author"], "Jane Roe")
        self.assertEqual(convert.office_props(FIXTURES / "plan.md"), {})  # not a zip

    def test_markdown_front_matter_then_first_heading(self):
        self.assertEqual(convert.markdown_props(recorded("plan.md"))["title"], "Quarterly Plan")
        self.assertEqual(convert.markdown_props("intro\n\n# The Heading\n")["title"], "The Heading")

    def test_pdf_title_from_the_largest_horizontal_line(self):
        def word(x0, y0, x1, y1, w):
            return f'<word xMin="{x0}" yMin="{y0}" xMax="{x1}" yMax="{y1}">{w}</word>'
        bbox = "".join([
            word(10, 200, 30, 400, "arXiv:1706.03762v7"),  # rotated margin stamp: tall and narrow
            word(100, 74, 150, 84.7, "Provided"), word(155, 74, 200, 84.7, "proper"),
            word(100, 150, 200, 165.5, "Attention"), word(205, 150, 240, 165.5, "Is"),
            word(100, 170, 200, 185.5, "All"), word(205, 170, 240, 185.5, "You&amp;Need"),
            word(100, 300, 300, 330, "Bigbutalone"),  # one word: no title line
        ])
        self.assertEqual(convert.pdf_title_from_layout(bbox), "Attention Is All You&Need")
        self.assertIsNone(convert.pdf_title_from_layout(""))

    def test_pdf_title_with_mixed_fonts_and_a_short_upright_word(self):
        # ACL 2023: the first title line mixes two fonts (heights 18.48 / 18.67, tops 66.90 / 66.96), the second
        # starts with "to" (taller than wide in a large font); two body words share that "to"'s x position.
        self.assertEqual(convert.pdf_title_from_layout(recorded("acl-2023-long-1.page1.bbox.html")),
                         "One Cannot Stand for Everyone! Leveraging Multiple User Simulators to train Task-oriented "
                         "Dialogue Systems")


class TestConvert(unittest.TestCase):
    def test_markdown_is_read(self):
        with tools(), mock.patch.object(convert, "run", side_effect=AssertionError("no tool")):
            doc = convert.convert(FIXTURES / "plan.md")
        self.assertEqual((doc.converter, doc.title, doc.author, doc.pages, doc.language),
                         ("read", "Quarterly Plan", "Jane Roe", None, None))

    def test_plain_text_is_fenced_and_has_no_heading_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, language in (("notes.txt", "text"), ("data.csv", "csv"), ("paper.tex", "latex")):
                path = Path(tmp) / name
                path.write_bytes("# not a heading\nCafé".encode("cp1252"))
                with tools(), mock.patch.object(convert, "run", side_effect=AssertionError("no tool")):
                    doc = convert.convert(path)
                self.assertEqual((doc.language, doc.title, doc.markdown), (language, None, "# not a heading\nCafé"))

    def test_pdf_with_pdftotext(self):
        run, calls = runner({"layout": recorded(LAYOUT),
                             "pdfinfo": "Title: A Tiny Paper on Pages\nAuthor: Ada Lovelace\n"
                                        "CreationDate: Wed Apr 10 23:11:43 2024 CEST\nPages: 3\n"})
        with tools("uvx", "pdftotext", "pdfinfo"), run:
            doc = convert.convert(PDF)
        self.assertEqual((doc.converter, len(doc.pages), doc.title, doc.author, doc.published),
                         ("pdftotext", 3, "A Tiny Paper on Pages", "Ada Lovelace", "2024-04-10"))
        self.assertIn("It is short on purpose and has a hyphenated word.", doc.pages[1])
        self.assertEqual(calls, ["layout", "pdfinfo"])

    def test_pdf_title_from_the_layout_pdftotext_already_read(self):
        run, calls = runner({"layout": recorded(LAYOUT), "pdfinfo": "Title:\nPages: 3\n"})
        with tools("pdftotext", "pdfinfo"), run:
            doc = convert.convert(PDF)
        self.assertEqual((doc.title, calls), ("A Tiny Paper on Pages", ["layout", "pdfinfo"]))

    def test_pdf_falls_back_to_markitdown(self):
        run, calls = runner({"markitdown": recorded("three-pages.markitdown.md")})
        with tools("uvx"), run:
            doc = convert.convert(PDF)
        self.assertEqual((doc.converter, len(doc.pages), calls), ("markitdown", 3, ["markitdown"]))
        self.assertEqual(doc.attempts, ["pdftotext: pdftotext is not installed"])
        self.assertIsNone(doc.title)  # no pdfinfo, no layout title: prepare.py falls back to the file name
        run, _ = runner({"layout": SkillError("Syntax Error"), "markitdown": recorded("three-pages.markitdown.md")})
        with tools("uvx", "pdftotext"), run:
            self.assertEqual(convert.convert(PDF).attempts, ["pdftotext: failed (Syntax Error)"])

    def test_pdf_without_any_converter_is_a_missing_tool(self):
        with tools(), self.assertRaisesRegex(MissingTool, "pdftotext, uvx missing"):
            convert.convert(PDF)

    def test_scanned_pdf(self):
        run, _ = runner({"markitdown": "\f\f", "layout": "<page></page><page></page>"})
        with tools("uvx", "pdftotext"), run, self.assertRaisesRegex(SkillError, "scanned PDF") as caught:
            convert.convert(PDF)
        self.assertNotIsInstance(caught.exception, MissingTool)

    def test_a_failure_next_to_a_missing_tool_is_no_missing_tool(self):
        run, _ = runner({"markitdown": SkillError("boom")})
        with tools("uvx"), run, self.assertRaisesRegex(SkillError, "installing pandoc may help") as caught:
            convert.convert(FIXTURES / "plan.docx")
        self.assertNotIsInstance(caught.exception, MissingTool)
        with tools(), self.assertRaisesRegex(MissingTool, "uvx, pandoc missing"):
            convert.convert(FIXTURES / "plan.docx")

    def test_docx_pptx_epub_with_markitdown(self):
        docs = {}
        for ext in (".docx", ".pptx", ".epub"):
            run, _ = runner({"markitdown": recorded(f"plan{ext}.markitdown.md")})
            with tools("uvx"), run:
                docs[ext] = convert.convert(FIXTURES / f"plan{ext}")
            self.assertEqual((docs[ext].converter, docs[ext].title, docs[ext].author),
                             ("markitdown", "Quarterly Plan", "Jane Roe"), ext)
        self.assertIn("## Slide 2", docs[".pptx"].markdown)
        self.assertNotIn("Slide number", docs[".pptx"].markdown)

    def test_pandoc_when_markitdown_fails(self):
        run, calls = runner({"markitdown": SkillError("boom"), "pandoc": "# Goals\n\nShip the thing.\n"})
        with tools("uvx", "pandoc"), run:
            doc = convert.convert(FIXTURES / "plan.docx")
        self.assertEqual((doc.converter, calls), ("pandoc", ["markitdown", "pandoc"]))
        self.assertEqual(doc.attempts, ["markitdown: failed (boom)"])

    def test_no_converter_for_a_pptx(self):
        run, _ = runner({"markitdown": SkillError("boom")})
        with tools("uvx", "pandoc"), run, self.assertRaisesRegex(SkillError, "could not convert plan.pptx"):
            convert.convert(FIXTURES / "plan.pptx")  # pandoc cannot read pptx


class TestLegacyFormats(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def file(self, name: str) -> Path:
        path = self.dir / name
        path.write_bytes(b"{\\rtf1\\ansi Hello}" if name.endswith(".rtf") else b"\xd0\xcf\x11\xe0")
        return path

    def test_rtf_goes_to_pandoc_first(self):
        run, calls = runner({"pandoc": "Hello from the RTF.\n"})
        with tools("uvx", "pandoc", "textutil"), run:
            doc = convert.convert(self.file("legacy.rtf"))
        self.assertEqual((doc.converter, calls), ("pandoc", ["pandoc"]))

    def test_raw_rtf_from_markitdown_is_no_conversion(self):
        run, _ = runner({"markitdown": "{\\rtf1\\ansi\\ansicpg1252 Hello}"})
        with tools("uvx"), run, self.assertRaisesRegex(SkillError, "markitdown: returned the raw RTF"):
            convert.convert(self.file("legacy.rtf"))
        run, calls = runner({"textutil": "Hello from the RTF.\n"})
        with tools("uvx", "textutil"), run:
            self.assertEqual(convert.convert(self.file("legacy.rtf")).converter, "textutil")

    def test_doc_with_textutil(self):
        run, calls = runner({"textutil": "Hello from Word 97.\n"})
        with tools("uvx", "textutil"), run:
            doc = convert.convert(self.file("legacy.doc"))
        self.assertEqual((doc.converter, doc.markdown, calls), ("textutil", "Hello from Word 97.\n", ["textutil"]))
        with tools("uvx"), self.assertRaisesRegex(SkillError, "macOS only") as caught:
            convert.convert(self.file("legacy.doc"))
        self.assertNotIsInstance(caught.exception, MissingTool)  # nothing to install on Linux

    def test_ppt_is_not_supported(self):
        with tools("uvx"), self.assertRaisesRegex(SkillError, "save it as .pptx"):
            convert.convert(self.file("old.ppt"))


if __name__ == "__main__":
    unittest.main()

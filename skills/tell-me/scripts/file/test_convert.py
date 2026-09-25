#!/usr/bin/env python3
"""Unit tests for file/convert.py (offline: markitdown, pdftotext and pandoc answer recorded output)."""
import sys
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


def recorded(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def tools(*present: str):
    """shutil.which answering only for `present`."""
    return mock.patch.object(convert.shutil, "which", side_effect=lambda t: f"/bin/{t}" if t in present else None)


def runner(answers: dict):
    """convert.run answering by the command's tool (markitdown, pdftotext, pdfinfo, pandoc); an Exception
    answer is raised. `calls` records the tools asked."""
    calls: list[str] = []

    def run(cmd):
        tool = "markitdown" if cmd[0] == "uvx" else cmd[0]
        key = "bbox" if "-bbox" in cmd else tool
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

    def test_split_pages(self):
        self.assertEqual(convert.split_pages("a\n\fb\n\fc\n\f"), ["a", "b", "c"])

    def test_pptx_slides(self):
        self.assertEqual(convert.pptx_slides("<!-- Slide number: 2 -->\n# Goals"), "## Slide 2\n# Goals")


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


class TestConvert(unittest.TestCase):
    def test_text_is_read(self):
        with tools(), mock.patch.object(convert, "run", side_effect=AssertionError("no tool")):
            doc = convert.convert(FIXTURES / "plan.md")
        self.assertEqual((doc.converter, doc.title, doc.author, doc.pages), ("read", "Quarterly Plan", "Jane Roe",
                                                                             None))

    def test_pdf_with_markitdown_pages(self):
        run, calls = runner({"markitdown": recorded("three-pages.markitdown.md"),
                             "pdfinfo": "Title: A Tiny Paper on Pages\nAuthor: Ada Lovelace\n"
                                        "CreationDate: Wed Apr 10 23:11:43 2024 CEST\nPages: 3\n"})
        with tools("uvx", "pdftotext", "pdfinfo"), run:
            doc = convert.convert(PDF)
        self.assertEqual((doc.converter, len(doc.pages), doc.title, doc.author, doc.published),
                         ("markitdown", 3, "A Tiny Paper on Pages", "Ada Lovelace", "2024-04-10"))
        self.assertIn("It is short on purpose and has a hyphenated word.", doc.pages[1])
        self.assertEqual(calls, ["markitdown", "pdfinfo"])

    def test_pdf_falls_back_to_pdftotext_without_uvx(self):
        run, calls = runner({"pdftotext": recorded("three-pages.pdftotext.txt"), "bbox": ""})
        with tools("pdftotext"), run:
            doc = convert.convert(PDF)
        self.assertEqual((doc.converter, len(doc.pages)), ("pdftotext", 3))
        self.assertEqual(doc.attempts, ["markitdown: uvx is missing"])
        self.assertIsNone(doc.title)  # no pdfinfo, no layout title: prepare.py falls back to the file name

    def test_pdf_without_any_converter_is_a_missing_tool(self):
        with tools(), self.assertRaises(MissingTool):
            convert.convert(PDF)

    def test_scanned_pdf(self):
        run, _ = runner({"markitdown": "\f\f", "pdftotext": "\f\f"})
        with tools("uvx", "pdftotext"), run, self.assertRaisesRegex(SkillError, "scanned PDF"):
            convert.convert(PDF)

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


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Unit tests for file/prepare.py (offline: the converter answers recorded output, downloads are mocked)."""
import contextlib
import email.message
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.append(str(HERE.parent / "shared"))

import convert  # noqa: E402
import prepare  # noqa: E402
from _common import SkillError  # noqa: E402

FIXTURES = HERE / "fixtures"


def pdf_doc() -> convert.Document:
    pages = convert.split_pages((FIXTURES / "three-pages.markitdown.md").read_text())
    return convert.Document("\n\n".join(pages), "markitdown", pages, "A Tiny Paper on Pages", "Ada Lovelace",
                            "2024-04-10")


class TestText(unittest.TestCase):
    def test_page_body(self):
        body = prepare.page_body(["one\n\ntwo", "", "three"], "original.pdf")
        self.assertEqual(body, "[p. 1](original.pdf#page=1) one\n\n[p. 1](original.pdf#page=1) two\n\n"
                               "[p. 2](original.pdf#page=2) *(no text on this page)*\n\n"
                               "[p. 3](original.pdf#page=3) three")

    def test_demote_keeps_fences(self):
        self.assertEqual(prepare.demote("# A\n```\n# not a heading\n```\n## B"),
                         "### A\n```\n# not a heading\n```\n#### B")

    def test_title_falls_back_to_the_file_name(self):
        doc = convert.Document("", "read", title="Microsoft Word - draft7.docx")
        self.assertEqual(prepare.title_of(doc, Path("/x/my_notes-2026.docx")), "my notes 2026")
        self.assertEqual(prepare.title_of(convert.Document("", "read", title="Real"), Path("a.md")), "Real")

    def test_file_name_of_a_download(self):
        def headers(ctype, disposition=None):
            h = email.message.Message()
            h["Content-Type"] = ctype
            if disposition:
                h["Content-Disposition"] = disposition
            return h
        self.assertEqual(prepare.file_name("https://arxiv.org/pdf/1706.03762", headers("application/pdf")),
                         "1706.03762.pdf")
        self.assertEqual(prepare.file_name("https://x.org/dl?id=3", headers(
            "application/pdf", 'attachment; filename="../Report 2026.pdf"')), "Report 2026.pdf")
        self.assertEqual(prepare.file_name("https://x.org/a/paper.pdf", headers("application/octet-stream")),
                         "paper.pdf")
        self.assertEqual(prepare.file_name("https://x.org/get/42", headers("application/octet-stream"),
                                           b"%PDF-1.5\n"), "42.pdf")

    def test_plain_text_goes_in_a_fence(self):
        doc = convert.Document("# not a heading\n```\ncode\n```", "read", language="text")
        meta = {"title": "notes", "url": "file:///x/notes.txt"}
        content = prepare.render_content(meta, {"original_file": "original.txt"}, doc)
        self.assertIn("## Document\n\n````text\n# not a heading\n```\ncode\n```\n````", content)
        self.assertNotIn("- words:", content)


class FakeResponse(io.BytesIO):
    """What urllib.request.urlopen returns, over `body`."""

    def __init__(self, body: bytes, ctype: str, length: int | None = None):
        super().__init__(body)
        self.headers = email.message.Message()
        self.headers["Content-Type"] = ctype
        if length is not None:
            self.headers["Content-Length"] = str(length)


class TestDownload(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def download(self, url: str, body: bytes, ctype: str, length: int | None = None) -> Path:
        with mock.patch.object(prepare.urllib.request, "urlopen", return_value=FakeResponse(body, ctype, length)):
            return prepare.download(url, self.dir)

    def test_a_pdf(self):
        path = self.download("https://arxiv.org/pdf/1810.04805", b"%PDF-1.5\n" + b"x" * 5000, "application/pdf")
        self.assertEqual((path.name, path.stat().st_size), ("1810.04805.pdf", 5009))

    def test_octet_stream_with_a_pdf_inside(self):
        self.assertEqual(self.download("https://x.org/get?id=3", b"%PDF-1.4 ...", "application/octet-stream").name,
                         "get.pdf")

    def test_the_size_limit_counts_the_bytes(self):
        with mock.patch.object(prepare, "MAX_DOWNLOAD", 10_000), \
                self.assertRaisesRegex(SkillError, "more than 0 MB"):
            self.download("https://x.org/big.pdf", b"%PDF-1.5" + b"x" * 20_000, "application/pdf")  # no length
        with mock.patch.object(prepare, "MAX_DOWNLOAD", 10_000), self.assertRaisesRegex(SkillError, "more than"):
            self.download("https://x.org/big.pdf", b"%PDF-1.5", "application/pdf", length=20_000)

    def test_an_html_page_instead_of_the_pdf(self):
        with self.assertRaisesRegex(SkillError, "sent an HTML page .* captcha"):
            self.download("https://x.org/paper.pdf", b"<!DOCTYPE html><title>Just a moment...</title>", "text/html")
        with self.assertRaisesRegex(SkillError, "sent an HTML page"):  # a wrong content type does not hide it
            self.download("https://x.org/slides.pptx", b"\n  <html><body>login</body></html>", "application/pdf")

    def test_a_pdf_url_that_serves_no_pdf(self):
        with self.assertRaisesRegex(SkillError, "is not a PDF"):
            self.download("https://x.org/paper.pdf", b"PK\x03\x04 a zip", "application/octet-stream")


class PrepareCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp)
        env = mock.patch.dict(os.environ, {"TELL_ME_ROOT": str(self.tmp / "lib")})
        env.start()
        self.addCleanup(env.stop)
        self.docs = self.tmp / "papers"
        self.docs.mkdir()

    def run_prepare(self, *argv: str, doc=None) -> dict:
        out = io.StringIO()
        with mock.patch.object(prepare, "convert", return_value=doc or pdf_doc()) as conv, \
                contextlib.redirect_stdout(out):
            prepare.main(list(argv))
        self.converted = conv.call_count
        return json.loads(out.getvalue())


class TestPrepare(PrepareCase):
    def test_pdf(self):
        pdf = self.docs / "tiny.pdf"
        shutil.copy(FIXTURES / "three-pages.pdf", pdf)
        env = self.run_prepare(str(pdf))
        folder = Path(env["dir"])
        self.assertEqual(folder, self.tmp / "lib" / "documents" / "papers" / "tiny")
        self.assertEqual((env["source"], env["kind"], env["doc_kind"], env["pages"], env["title"], env["author"]),
                         ("file", "document", "pdf", 3, "A Tiny Paper on Pages", "Ada Lovelace"))
        self.assertEqual((folder / "original.pdf").read_bytes(), pdf.read_bytes())
        content = (folder / "content.md").read_text()
        self.assertIn("- original: [original.pdf](original.pdf)", content)
        self.assertIn("[p. 2](original.pdf#page=2) The second page holds the method. It is short on purpose",
                      content)
        meta = json.loads((folder / "metadata.json").read_text())
        self.assertEqual((meta["source"], meta["url"], meta["site"], meta["published"], meta["extractor"]),
                         ("file", pdf.resolve().as_uri(), "local", "2024-04-10", "markitdown"))
        self.assertEqual(meta["id"], prepare.sha256(pdf))
        self.assertEqual(meta["extras"]["original_path"], str(pdf))

    def test_the_same_content_is_reused_under_any_name(self):
        pdf = self.docs / "tiny.pdf"
        shutil.copy(FIXTURES / "three-pages.pdf", pdf)
        first = self.run_prepare(str(pdf))
        moved = self.tmp / "elsewhere.pdf"
        shutil.copy(pdf, moved)
        again = self.run_prepare(str(moved))
        self.assertEqual((again["dir"], again["reused"], self.converted), (first["dir"], True, 0))
        meta = json.loads((Path(first["dir"]) / "metadata.json").read_text())
        self.assertEqual(meta["extras"]["aliases"], sorted([str(pdf), str(moved)]))
        refreshed = self.run_prepare(str(pdf), "--refresh")
        self.assertEqual((refreshed["dir"], self.converted), (first["dir"], 1))

    def md(self, name: str, text: str, title: str | None = "Notes") -> tuple[Path, convert.Document]:
        path = self.docs / name
        path.write_text(text)
        return path, convert.Document(text, "read", title=title)

    def test_a_changed_file_is_a_new_version_in_the_same_folder(self):
        md, doc = self.md("notes.md", "# Notes\n\nfirst draft\n")
        first = self.run_prepare(str(md), doc=doc)
        folder, old_id = Path(first["dir"]), first["id"]
        fetched = json.loads((folder / "metadata.json").read_text())["fetched"]
        (folder / "summary.md").write_text("see [original.md](original.md)")
        (folder / "summary.html").write_text('<a href="original.md">')
        prepare.update_json(folder / "metadata.json", {"summary": {"mode": "tldr"}})
        md, doc = self.md("notes.md", "# Notes\n\nsecond draft, much longer now\n")
        second = self.run_prepare(str(md), doc=doc)
        self.assertEqual((second["dir"], second["changed"], second["reused"], second["summary_exists"]),
                         (first["dir"], True, True, False))
        self.assertNotEqual(second["id"], old_id)
        short = old_id[:8]
        self.assertEqual(second["versions"], [{"sha256": old_id, "prepared": fetched,
                                               "original_file": f"original.{short}.md",
                                               "summary_file": f"summary.{short}.md", "summary": {"mode": "tldr"}}])
        self.assertEqual((folder / f"summary.{short}.md").read_text(),
                         f"see [original.{short}.md](original.{short}.md)")  # its links follow the kept original
        self.assertTrue((folder / f"summary.{short}.html").exists())
        self.assertEqual((folder / f"original.{short}.md").read_text(), "# Notes\n\nfirst draft\n")
        self.assertEqual((folder / "original.md").read_text(), md.read_text())
        meta = json.loads((folder / "metadata.json").read_text())
        self.assertNotIn("summary", meta)
        content = Path(second["content_file"]).read_text()
        self.assertIn("### Notes\n\nsecond draft", content)  # the document's heading below ## Document
        self.assertEqual(meta["word_count"], len(content.split()))

    def test_another_document_under_a_reused_name_gets_its_own_folder(self):
        pdf = self.docs / "paper.pdf"
        pdf.write_bytes(b"%PDF-1 first")
        first = self.run_prepare(str(pdf))  # "A Tiny Paper on Pages"
        pdf.write_bytes(b"%PDF-1 second")
        other = convert.Document("Completely different words about gardening and tomatoes.", "pdftotext",
                                 ["Completely different words about gardening and tomatoes."], "Growing Tomatoes")
        second = self.run_prepare(str(pdf), doc=other)
        self.assertNotEqual(second["dir"], first["dir"])
        self.assertEqual((second["reused"], second.get("changed"), second["title"]), (False, None, "Growing Tomatoes"))
        old_meta = json.loads((Path(first["dir"]) / "metadata.json").read_text())
        self.assertEqual(old_meta["extras"]["aliases"], [])  # the path names the new document now
        self.assertTrue((Path(first["dir"]) / "original.pdf").read_bytes().endswith(b"first"))
        again = self.run_prepare(str(pdf), doc=other)
        self.assertEqual((again["dir"], self.converted), (second["dir"], 0))
        # --refresh is the evidence that it is a new version of the first one
        pdf.write_bytes(b"%PDF-1 third")
        third = self.run_prepare(str(pdf), "--refresh", doc=other)
        self.assertEqual((third["dir"], third["changed"]), (second["dir"], True))

    def test_an_untitled_document_with_mostly_the_same_words_is_a_new_version(self):
        text = "one two three four five six seven eight nine ten\n"
        txt, doc = self.md("log.txt", text, title=None)
        first = self.run_prepare(str(txt), doc=doc)
        txt, doc = self.md("log.txt", text + "eleven\n", title=None)
        self.assertEqual(self.run_prepare(str(txt), doc=doc)["dir"], first["dir"])

    def test_no_ping_pong_between_two_paths_that_had_the_same_content(self):
        a, doc = self.md("a.md", "# Notes\n\nsame\n")
        (self.tmp / "other").mkdir()
        b = self.tmp / "other" / "a.md"
        b.write_text(a.read_text())
        first = self.run_prepare(str(a), doc=doc)
        self.assertEqual(self.run_prepare(str(b), doc=doc)["dir"], first["dir"])  # same content: one folder
        b.write_text("# Notes\n\nsame, edited\n")
        edited = convert.Document(b.read_text(), "read", title="Notes")
        self.assertEqual(self.run_prepare(str(b), doc=edited)["changed"], True)
        meta = json.loads((Path(first["dir"]) / "metadata.json").read_text())
        self.assertEqual(meta["extras"]["aliases"], [str(b)])  # a has the earlier content
        a_again = self.run_prepare(str(a), doc=doc)
        self.assertNotEqual(a_again["dir"], first["dir"])
        for path, d, folder in ((a, doc, a_again["dir"]), (b, edited, first["dir"]), (a, doc, a_again["dir"])):
            env = self.run_prepare(str(path), doc=d)
            self.assertEqual((env["dir"], env["reused"], env.get("changed"), self.converted), (folder, True, None, 0))
        versions = json.loads((Path(first["dir"]) / "metadata.json").read_text())["extras"]["versions"]
        self.assertEqual(len(versions), 1)

    def test_the_librarys_own_copy_can_be_prepared_again(self):
        pdf = self.docs / "tiny.pdf"
        shutil.copy(FIXTURES / "three-pages.pdf", pdf)
        first = self.run_prepare(str(pdf))
        env = self.run_prepare(str(Path(first["dir"]) / "original.pdf"), "--refresh")  # no SameFileError
        self.assertEqual((env["dir"], self.converted), (first["dir"], 1))
        self.assertEqual((Path(first["dir"]) / "original.pdf").read_bytes(), pdf.read_bytes())

    def test_a_url_is_downloaded(self):
        def fake_download(url, into):
            target = into / "1706.03762.pdf"
            shutil.copy(FIXTURES / "three-pages.pdf", target)
            return target
        with mock.patch.object(prepare, "download", side_effect=fake_download):
            env = self.run_prepare("https://arxiv.org/pdf/1706.03762")
        meta = json.loads((Path(env["dir"]) / "metadata.json").read_text())
        self.assertEqual((meta["url"], meta["site"]), ("https://arxiv.org/pdf/1706.03762", "arxiv.org"))
        self.assertNotIn("original_path", meta["extras"])
        self.assertEqual(Path(env["dir"]), self.tmp / "lib" / "documents" / "arxiv-org" / "1706-03762")
        self.assertTrue((Path(env["dir"]) / "original.pdf").exists())
        self.assertIn("- source: https://arxiv.org/pdf/1706.03762", Path(env["content_file"]).read_text())

    def test_not_a_document(self):
        clip = self.docs / "clip.mp4"
        clip.write_bytes(b"\0")
        with self.assertRaisesRegex(SkillError, "is a video input, not a document"):
            self.run_prepare(str(clip))


if __name__ == "__main__":
    unittest.main()

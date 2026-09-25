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

    def test_a_changed_file_is_a_new_version_in_the_same_folder(self):
        md = self.docs / "notes.md"
        md.write_text("# Notes\n\nfirst draft\n")
        doc1 = convert.Document("# Notes\n\nfirst draft\n", "read", title="Notes")
        first = self.run_prepare(str(md), doc=doc1)
        old_id = first["id"]
        md.write_text("# Notes\n\nsecond draft\n")
        second = self.run_prepare(str(md), doc=convert.Document("# Notes\n\nsecond draft\n", "read", title="Notes"))
        self.assertEqual((second["dir"], second["changed"], second["reused"]), (first["dir"], True, True))
        self.assertNotEqual(second["id"], old_id)
        self.assertEqual([v["sha256"] for v in second["versions"]], [old_id])
        content = Path(second["content_file"]).read_text()
        self.assertIn("### Notes\n\nsecond draft", content)  # the document's heading below ## Document

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

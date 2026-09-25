#!/usr/bin/env python3
"""Unit tests for prepare.py (the dispatcher) and the source contract in _common.py (offline)."""
import json
import tempfile
import unittest
from pathlib import Path

from _common import CONTRACT_KEYS, ENVELOPE_KEYS, SkillError, contract, envelope
from prepare import dispatch

FAKE_SOURCE = '''
import json, sys
print(json.dumps({"source": "web", "kind": "page", "dir": "/d", "id": sys.argv[1], "title": "T", "url": sys.argv[1],
                  "content_file": "/d/content.md", "summary": "/d/summary.md", "summary_exists": False,
                  "subskill": "s", "template": "t", "flags": sys.argv[2:]}))
'''


class TestDispatch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def source(self, name: str, code: str) -> None:
        (self.dir / name).mkdir()
        (self.dir / name / "prepare.py").write_text(code)

    def test_runs_the_routed_source_with_its_flags(self):
        self.source("web", FAKE_SOURCE)
        code, env = dispatch("https://example.com/post", ["--x", "1"], self.dir)
        self.assertEqual(code, 0)
        self.assertEqual((env["source"], env["url"], env["flags"]), ("web", "https://example.com/post", ["--x", "1"]))

    def test_unbuilt_source_is_not_supported_yet(self):
        with self.assertRaisesRegex(SkillError, "source 'web' not supported yet"):
            dispatch("https://example.com", [], self.dir)

    def test_unbuilt_url_source_falls_back_to_video(self):
        self.source("video", FAKE_SOURCE.replace('"source": "web"', '"source": "video"'))
        code, env = dispatch("https://x.com/jack/status/20", [], self.dir)
        self.assertEqual((code, env["source"], env["url"]), (0, "video", "https://x.com/jack/status/20"))

    def test_flags_before_the_input_are_rejected(self):
        from prepare import main
        with self.assertRaises(SystemExit):
            main(["--lang", "de", "https://example.com"])

    def test_exit_code_passes_through(self):
        self.source("web", "import sys; sys.exit(2)")
        self.assertEqual(dispatch("https://example.com", [], self.dir), (2, None))

    def test_incomplete_envelope_is_an_error(self):
        self.source("web", "print('{\"source\": \"web\"}')")
        with self.assertRaisesRegex(SkillError, "missing kind"):
            dispatch("https://example.com", [], self.dir)

    def test_list_envelope_needs_fewer_keys(self):
        self.source("video", "import json; print(json.dumps({'source': 'video', 'kind': 'playlist', 'dir': '/d', "
                             "'title': 'P', 'subskill': 's', 'videos': []}))")
        self.assertEqual(dispatch("https://www.youtube.com/playlist?list=PL1", [], self.dir)[1]["kind"], "playlist")


class TestContract(unittest.TestCase):
    def test_legacy_video_metadata_maps_to_the_contract(self):
        meta = {"id": "abc", "title": "T", "channel": "Chan", "webpage_url": "https://youtu.be/abc",
                "upload_date": "20260924", "duration": 61, "platform": "youtube", "transcript_source": "captions",
                "prepared_at": "2026-09-25T10:00:00"}
        self.assertEqual(contract(meta), {
            "source": "video", "id": "abc", "url": "https://youtu.be/abc", "title": "T", "author": "Chan",
            "published": "2026-09-24", "fetched": "2026-09-25T10:00:00", "site": "youtube", "word_count": None,
            "duration": 61, "extractor": "captions", "content_file": "content.md", "extras": {}})

    def test_contract_fields_win_over_legacy_keys(self):
        c = contract({"source": "web", "url": "https://a.b/", "webpage_url": "https://old/", "content_file": "content.md"})
        self.assertEqual((c["source"], c["url"], c["content_file"]), ("web", "https://a.b/", "content.md"))
        self.assertEqual(set(c), set(CONTRACT_KEYS))

    def test_envelope(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "content.md").write_text("one two three")
            env = envelope(folder, {"source": "web", "id": "x", "title": "T", "url": "u", "content_file": "content.md"},
                           "page", extra=1)
            self.assertTrue(set(ENVELOPE_KEYS) <= set(env))
            self.assertEqual((env["content_words"], env["summary_exists"], env["extra"]), (3, False, 1))
            self.assertTrue(env["subskill"].endswith("subskills/web/SUBSKILL.md"))
            self.assertTrue(env["template"].endswith("templates/web/template.md"))


if __name__ == "__main__":
    unittest.main()

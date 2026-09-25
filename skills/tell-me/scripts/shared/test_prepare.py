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

    def argparse_source(self, name: str, flags: list[str], fail: str | None = None, big: bool = False) -> None:
        """A source script with argparse (so --help lists its flags; `--x=` takes a value) that echoes its argv in
        the envelope. `fail`: it logs the message the way run_main does and exits 1."""
        opts = "".join(f"ap.add_argument({f.rstrip('=')!r})\n" if f.endswith("=") else
                       f"ap.add_argument({f!r}, action='store_true')\n" for f in flags)
        body = (f"sys.stderr.write('[tell-me] progress\\n[tell-me] {fail}\\n'); sys.exit(1)\n" if fail else
                "print(json.dumps({'source': %r, 'kind': 'page', 'dir': '/d/' + %r + a.input[-1], 'id': a.input, "
                "'title': %r, 'url': a.input, 'content_file': '/d/c.md', 'summary': '/d/s.md', "
                "'summary_exists': False, 'subskill': 's', 'template': 't', 'argv': sys.argv[2:]%s}))\n"
                % (name, name, name.upper(), ", 'pad': 'x' * 300000" if big else ""))
        self.source(name, "import argparse, json, sys\nap = argparse.ArgumentParser()\nap.add_argument('input')\n"
                    + opts + "a = ap.parse_args()\n" + body)

    def many(self, inputs: list[str], flags: list[str]):
        from prepare import prepare_many
        return prepare_many(inputs, flags, self.dir, root=self.dir / "lib")

    def test_several_inputs_each_source_gets_its_own_flags(self):
        self.argparse_source("web", ["--refresh"])
        self.argparse_source("hn", ["--no-article", "--refresh", "--lang="])
        code, out = self.many(["https://example.com/a", "https://news.ycombinator.com/item?id=1"],
                              ["--no-article", "--refresh", "--lang", "de"])
        self.assertEqual(code, 0)
        self.assertEqual([i["argv"] for i in out["items"]], [["--refresh"], ["--no-article", "--refresh", "--lang", "de"]])
        digest = Path(out["digest_dir"])
        self.assertEqual(digest.parent, self.dir / "lib" / "digests")
        self.assertTrue(digest.name.endswith("-web-and-1-more"))
        meta = json.loads((digest / "metadata.json").read_text())
        self.assertEqual((meta["kind"], meta["title"], [i["source"] for i in meta["items"]]),
                         ("digest", "WEB · HN", ["web", "hn"]))
        self.assertTrue(out["template"].endswith("templates/shared/digest.md"))
        self.assertFalse(out["digest_exists"])
        # a saved digest keeps its record when the same inputs are prepared again
        (digest / "metadata.json").write_text(json.dumps(meta | {"summary": {"mode": "digest"}}))
        (digest / "digest.md").write_text("x")
        code, out = self.many(["https://example.com/a", "https://news.ycombinator.com/item?id=1"], [])
        self.assertEqual(Path(out["digest_dir"]), digest)
        self.assertTrue(out["digest_exists"])
        self.assertEqual(json.loads((digest / "metadata.json").read_text())["summary"], {"mode": "digest"})

    def test_a_failing_input_does_not_stop_the_others(self):
        self.argparse_source("web", [])
        self.argparse_source("hn", [], fail="Hacker News has no item 1")
        code, out = self.many(["https://news.ycombinator.com/item?id=1", "https://example.com/a"], [])
        self.assertEqual(code, 0)
        self.assertEqual(out["items"][0], {"input": "https://news.ycombinator.com/item?id=1",
                                           "error": "Hacker News has no item 1", "exit_code": 1})
        self.assertEqual(out["items"][1]["source"], "web")
        self.assertIsNone(out["digest_dir"])  # one input left: nothing to digest
        code, out = self.many(["https://news.ycombinator.com/item?id=1", "nosuchfile.pdf"], [])
        self.assertEqual((code, out["items"][1]["exit_code"]), (1, 1))
        self.assertIn("no such file", out["items"][1]["error"])

    def test_misplaced_inputs_and_unknown_flags_are_errors(self):
        self.argparse_source("web", ["--refresh", "--lang="])
        a, b = "https://example.com/a", "https://example.com/b"
        with self.assertRaisesRegex(SkillError, "'https://example.com/c' after the flags"):
            self.many([a, b], ["--refresh", "https://example.com/c"])
        with self.assertRaisesRegex(SkillError, "--refersh is a flag none"):
            self.many([a, b], ["--refersh"])
        code, out = self.many([a, b], ["--lang", "de", "--refresh"])  # a value is not an input
        self.assertEqual([i["argv"] for i in out["items"]], [["--lang", "de", "--refresh"]] * 2)
        code, out = self.many([a, b], ["--lang=de"])
        self.assertEqual(out["items"][0]["argv"], ["--lang=de"])

    def test_a_usage_error_is_exit_1_not_a_missing_tool(self):
        self.argparse_source("web", ["--lang="])
        errors = []
        code, env = dispatch("https://example.com/a", ["--lang"], self.dir, errors)  # no value
        self.assertEqual((code, env), (1, None))
        self.assertIn("expected one argument", errors[0])

    def test_a_big_envelope_does_not_block(self):
        self.argparse_source("web", [], big=True)
        code, env = dispatch("https://example.com/a", [], self.dir, [])
        self.assertEqual((code, len(env["pad"])), (0, 300000))

    def test_the_same_input_twice_is_prepared_once(self):
        self.argparse_source("web", [])
        code, out = self.many(["https://example.com/a", "https://example.com/a", "https://example.com/b"], [])
        self.assertEqual([i["url"] for i in out["items"]], ["https://example.com/a", "https://example.com/b"])

    def test_known_flags_from_the_usage_block(self):
        from prepare import known_flags
        self.argparse_source("video", ["--lang=", "--skip-download"])
        self.assertEqual(known_flags(self.dir / "video" / "prepare.py"), {"--lang": True, "--skip-download": False})

    def test_error_of(self):
        from prepare import error_of
        self.assertEqual(error_of(["[tell-me] fetching", "[tell-me] HTTP 404 for https://x", ""]),
                         "HTTP 404 for https://x")
        self.assertEqual(error_of(["usage: p [-h] url", "p: error: unrecognized arguments: --x"]),
                         "unrecognized arguments: --x")
        self.assertEqual(error_of([]), "failed")

    def test_no_input_is_a_usage_error(self):
        from prepare import main
        with self.assertRaises(SystemExit):
            main([])

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

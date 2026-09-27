#!/usr/bin/env python3
"""Unit tests for topic/prepare.py (offline: the searches answer from the recorded fixtures)."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import prepare  # noqa: E402
import search  # noqa: E402
from _common import MissingTool, SkillError  # noqa: E402

FIX = HERE / "fixtures"


def fake_run(kind, query, limit, dirs=None):
    """The recorded answers (all recorded for "open knowledge format"), tagged with the asked query."""
    if kind == "video":
        found = search.parse_videos(json.loads((FIX / "video.ytsearch.json").read_text()), query)
    elif kind == "web":
        found = search.parse_bing((FIX / "web.bing.rss").read_text(), query)
    elif kind == "github":
        found = search.parse_github(json.loads((FIX / "github.search.json").read_text()), query)
    elif kind == "hn":
        found = search.parse_hn(json.loads((FIX / "hn.algolia.json").read_text()), query)
    else:
        raise SkillError("Spotlight is off")
    return found[:limit]


def cand(source, id_, query="q"):
    return {"input": f"https://e.com/{id_}", "title": id_, "source": source, "kind": "k", "id": id_, "query": query}


class TestMerge(unittest.TestCase):
    def test_searches_take_turns_and_items_are_listed_once(self):
        a = [cand("hn", "1", "okf"), cand("hn", "2", "okf"), cand("hn", "3", "okf")]
        b = [cand("hn", "9", "full"), cand("hn", "2", "full")]
        out = prepare.merge([a, b], 3, {})
        self.assertEqual([(c["id"], c["query"]) for c in out["hn"]], [("1", "okf"), ("9", "full"), ("2", "okf")])
        self.assertEqual(set(out), set(prepare.BUCKETS))

    def test_library_items_are_marked(self):
        out = prepare.merge([[cand("web", "a"), cand("web", "b")]], 5, {("web", "b"): Path("/lib/b")})
        self.assertEqual([(c["summary_exists"], c.get("dir")) for c in out["web"]], [(False, None), (True, "/lib/b")])


class TestMain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve() / "lib"
        env = mock.patch.dict(os.environ, {"TELL_ROOT": str(self.root)})
        env.start()
        self.addCleanup(env.stop)

    def summarized(self, rel: str, meta: dict, summary: str) -> Path:
        folder = self.root / rel
        folder.mkdir(parents=True)
        (folder / "metadata.json").write_text(json.dumps(meta))
        (folder / "summary.md").write_text(summary)
        return folder

    def run_main(self, *args) -> tuple[dict, str]:
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(search, "run", side_effect=fake_run), \
                mock.patch.object(prepare, "require"), redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(prepare.main(list(args)), 0)
        return json.loads(out.getvalue()), err.getvalue()

    def test_envelope_folder_and_candidates(self):
        repo = self.summarized("repos/github/googlecloudplatform/open-knowledge-format",
                               {"source": "github", "id": "GoogleCloudPlatform/open-knowledge-format",
                                "url": "https://github.com/GoogleCloudPlatform/open-knowledge-format", "title": "OKF"},
                               "# OKF\nthe spec repo")
        self.summarized("articles/blog/other", {"source": "web", "id": "https://blog.dev/okf-notes",
                                                "url": "https://blog.dev/okf-notes", "title": "Notes"},
                        "Notes on OKF, the open knowledge format.")
        self.summarized("articles/blog/unrelated", {"source": "web", "id": "https://blog.dev/bokf",
                                                    "url": "https://blog.dev/bokf", "title": "bokfx"}, "bokfx")
        env, err = self.run_main("okf", "--also", "open knowledge format", "--limit", "4")
        folder = self.root / "topics" / "okf"
        self.assertEqual((env["source"], env["kind"], env["dir"], env["title"]), ("topic", "topic", str(folder), "okf"))
        self.assertEqual(env["queries"], ["okf", "open knowledge format"])
        self.assertTrue(env["subskill"].endswith("subskills/topic/SUBSKILL.md"))
        self.assertTrue(env["template"].endswith("templates/topic/template.md"))
        self.assertFalse(env["digest_exists"])
        c = env["candidates"]
        self.assertEqual({k: len(v) for k, v in c.items() if v}, env["counts"])
        self.assertTrue(all(len(v) <= 4 for v in c.values()))
        # the library match comes first, the repo the GitHub search found too is listed once and marked
        self.assertEqual(c["web"][0]["input"], "https://blog.dev/okf-notes")
        self.assertEqual(c["web"][0]["found"], "library")
        self.assertNotIn("https://blog.dev/bokf", [x["input"] for x in c["web"]])  # "okf" as a whole word only
        gh = [x for x in c["github"] if x["id"] == "GoogleCloudPlatform/open-knowledge-format"]
        self.assertEqual((len(gh), gh[0]["summary_exists"], gh[0]["dir"]), (1, True, str(repo)))
        # the Spotlight failure and the X note are reported; the other searches went on
        self.assertTrue(any(n.startswith("file (okf): Spotlight is off") for n in env["notes"]))
        self.assertTrue(any(n.startswith("x: X has no search") for n in env["notes"]))
        meta = json.loads((folder / "metadata.json").read_text())
        self.assertEqual((meta["source"], meta["kind"], meta["title"], meta["items"], meta["content_file"]),
                         ("topic", "digest", "okf", [], "candidates.md"))
        self.assertEqual(json.loads((folder / "candidates.json").read_text())["candidates"], c)
        md = (folder / "candidates.md").read_text()
        self.assertIn("## Hacker News threads", md)
        self.assertIn("summarized", md)
        self.assertIn("searching video, web, github, hn, file for okf / open knowledge format", err)

    def test_a_second_search_keeps_the_chosen_items_and_title(self):
        folder = self.root / "topics" / "okf"
        folder.mkdir(parents=True)
        (folder / "metadata.json").write_text(json.dumps({"source": "topic", "kind": "digest", "title": "okf",
                                                          "items": [{"url": "u"}], "summary": {"mode": "digest"}}))
        (folder / "digest.md").write_text("x")
        env, _ = self.run_main("topic:okf", "--only", "hn")
        meta = json.loads((folder / "metadata.json").read_text())
        self.assertEqual((meta["items"], meta["summary"]), ([{"url": "u"}], {"mode": "digest"}))
        self.assertTrue(env["digest_exists"])
        self.assertEqual([k for k, v in env["candidates"].items() if v], ["hn"])

    def test_unknown_kind_is_an_error(self):
        with self.assertRaisesRegex(SkillError, "unknown kind"):
            self.run_main("okf", "--only", "hn,tiktok")

    def test_missing_ytdlp_stops_but_a_missing_rg_is_a_note(self):
        notes = []

        def missing(kind, *a):
            raise MissingTool(f"missing required tool(s): {'yt-dlp' if kind == 'video' else 'rg'}")
        with mock.patch.object(search, "run", side_effect=missing):
            self.assertEqual(prepare.run_searches(["okf"], ["file"], 3, None, notes), [[]])
            self.assertIn("rg", notes[0])
            self.assertIn("install-prerequisites.sh", notes[0])
            with self.assertRaises(MissingTool):
                prepare.run_searches(["okf"], ["video"], 3, None, notes)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Unit tests for github/thread.py and github/related.py (offline: recorded API answers)."""
import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import prepare  # noqa: E402
import related  # noqa: E402
import thread  # noqa: E402
from _common import CONTRACT_KEYS, ENVELOPE_KEYS, SkillError, read_json, write_json  # noqa: E402
from client import NotFound  # noqa: E402
from fake_github import REPO, FakeGitHub, load  # noqa: E402

ISSUE, PULL, DISCUSSION = load("issue.api.json"), load("pull.api.json"), load("discussion.api.json")
LINE = re.compile(r"^- \*\*[\w.\[\]-]+\*\* \[→\]\(https://github\.com/\S+\) \(\d{4}-\d\d-\d\d[^)]*\): ", re.M)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        env = mock.patch.dict(os.environ, {"TELL_ME_ROOT": self.tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(self.tmp.cleanup)
        self.gh = FakeGitHub(ISSUE | PULL | DISCUSSION)

    def run_main(self, *args):
        out = io.StringIO()
        with mock.patch.object(prepare, "GitHub", return_value=self.gh), mock.patch.object(prepare, "log"), \
                mock.patch.object(thread, "log"), redirect_stdout(out):
            self.assertEqual(prepare.main(list(args)), 0)
        return json.loads(out.getvalue())


class TestText(unittest.TestCase):
    def test_clean_drops_template_comments_and_turns_headings_bold(self):
        body = "<!-- fill this in -->\r\n## Summary\r\n\r\n\r\n\r\nFixes it.\r\n```\r\n# shell comment\r\n```"
        self.assertEqual(thread.clean(body), "**Summary**\n\nFixes it.\n```\n# shell comment\n```")

    def test_pasted_screenshots_become_markdown_images(self):
        body = '<img width="2560" height="1600" alt="Image" src="https://github.com/user-attachments/assets/f3" />'
        self.assertEqual(thread.clean(body), "![image](https://github.com/user-attachments/assets/f3)")

    def test_deleted_account_is_ghost(self):
        self.assertEqual(thread.login(None), "ghost")


class TestIssue(Base):
    def test_issue_folder_content_and_contract(self):
        env = self.run_main("https://github.com/kepano/defuddle/issues/375")
        folder = self.root / "repos" / "github" / "kepano" / "defuddle" / "issues" / "375-projectorjunkies-missing-data"
        self.assertEqual((env["dir"], env["kind"], env["number"], env["comments"]), (str(folder), "issue", 375, 11))
        self.assertTrue(set(ENVELOPE_KEYS) <= set(env))
        meta = read_json(folder / "metadata.json")
        self.assertTrue(set(CONTRACT_KEYS) <= set(meta))
        self.assertEqual((meta["id"], meta["extras"]["repo"], meta["extras"]["state"]), (f"{REPO}#375", REPO, "open"))
        content = (folder / "content.md").read_text()
        self.assertTrue(content.startswith(f"# Projectorjunkies missing data ({REPO}#375)\n"))
        self.assertIn("\n## Issue\n\n- **", content)
        self.assertEqual(len(LINE.findall(content)), 12)  # the issue and its 11 comments
        dates = re.findall(r"^- \*\*\S+\*\* \[→\]\(\S+#issuecomment-\d+\) \((\S+?)[,)]", content, re.M)
        self.assertEqual(dates, sorted(dates))

    def test_url_case_is_canonicalized_and_kept_as_alias(self):
        for k in [k for k in ISSUE if k.startswith("repos/kepano/")]:
            self.gh.answers[k.replace("repos/kepano/defuddle", "repos/Kepano/Defuddle")] = ISSUE[k]
        first = self.run_main("https://github.com/kepano/defuddle/issues/375")
        env = self.run_main("https://github.com/Kepano/Defuddle/issues/375", "--refresh")
        self.assertEqual((env["dir"], env["id"], env["reused"]), (first["dir"], f"{REPO}#375", True))
        meta = read_json(Path(env["dir"]) / "metadata.json")
        self.assertEqual((meta["extras"]["repo"], meta["extras"]["aliases"]), (REPO, ["Kepano/Defuddle#375"]))
        calls = len(self.gh.calls)
        again = self.run_main("https://github.com/Kepano/Defuddle/issues/375")  # the alias finds it, no fetch
        self.assertEqual((again["dir"], again["reused"], len(self.gh.calls)), (first["dir"], True, calls))
        self.assertEqual(len(list((self.root / "repos").rglob("metadata.json"))), 1)

    def test_a_transferred_issue_lives_in_its_new_repo(self):
        issue = json.loads(json.dumps(ISSUE["repos/kepano/defuddle/issues/375"]))
        issue |= {"html_url": "https://github.com/obsidianmd/clipper/issues/12", "number": 12,
                  "repository_url": "https://api.github.com/repos/obsidianmd/clipper"}
        self.gh.answers = {"repos/kepano/defuddle/issues/375": issue,
                           "repos/obsidianmd/clipper/issues/12/comments?per_page=100&page=1": []}
        env = self.run_main("https://github.com/kepano/defuddle/issues/375")
        self.assertIn("/repos/github/obsidianmd/clipper/issues/12-", env["dir"])
        meta = read_json(Path(env["dir"]) / "metadata.json")
        self.assertEqual((meta["id"], meta["extras"]["aliases"]), ("obsidianmd/clipper#12", [f"{REPO}#375"]))

    def test_rerun_reuses(self):
        first = self.run_main("https://github.com/kepano/defuddle/issues/375")
        calls = len(self.gh.calls)
        again = self.run_main("https://github.com/kepano/defuddle/issues/375")
        self.assertEqual((again["dir"], again["reused"], len(self.gh.calls)), (first["dir"], True, calls))


class TestPull(Base):
    def test_pull_request_with_files_reviews_and_line_comments(self):
        env = self.run_main("https://github.com/astral-sh/uv/pull/21966")
        self.assertEqual((env["kind"], env["state"]), ("pull", "closed"))
        self.assertIn("/astral-sh/uv/pulls/21966-bench-attempt-to-stabilize-digest-benchmarks", env["dir"])
        content = Path(env["content_file"]).read_text()
        self.assertIn("- state: merged\n", content)
        self.assertIn("- branch: astral-sh:ww/fix-bench → main\n- diff: +28 −14 in 1 file\n", content)
        self.assertIn("## Pull request\n\n- **woodruffw** [→](https://github.com/astral-sh/uv/pull/21966) (2026-09-24): "
                      "**Summary**", content)
        self.assertIn("## Files changed\n\n- `crates/uv-bench/benches/uv_pypi_types.rs` (modified, +28 −14)", content)
        self.assertRegex(content, r"#discussion_r\d+\) \(2026-09-24, on crates/uv-bench/benches/uv_pypi_types\.rs:\d+\)")
        self.assertRegex(content, r"#pullrequestreview-\d+\) \([\d-]+, approved\)")

    def test_a_pending_review_is_left_out(self):
        key = "repos/astral-sh/uv/pulls/21966/reviews?per_page=100&page=1"
        self.gh.answers[key] = PULL[key] + [{"state": "PENDING", "submitted_at": None, "body": "draft thoughts",
                                              "user": {"login": "me"}, "html_url": "https://github.com/x#r"}]
        with mock.patch.object(thread, "log"):
            t = thread.fetch_issue(self.gh, {"repo": "astral-sh/uv", "number": 21966})
        self.assertNotIn("draft thoughts", [c["body"] for c in t["comments"]])
        dates = [c["date"] for c in t["comments"]]
        self.assertEqual(dates, sorted(dates))

    def test_an_issue_link_to_a_pull_request_is_a_pull_request(self):
        env = self.run_main("https://github.com/astral-sh/uv/issues/21966")
        self.assertEqual(env["kind"], "pull")


class TestDiscussion(Base):
    def test_discussion_comments_with_upvotes(self):
        env = self.run_main("https://github.com/tailwindlabs/tailwindcss/discussions/307")
        self.assertEqual((env["kind"], env["comments"]), ("discussion", 3))
        content = Path(env["content_file"]).read_text()
        self.assertIn("- category: Ideas\n", content)
        self.assertIn("- upvotes: 2\n", content)  # the discussion's upvoteCount, not reactions
        self.assertNotIn("- reactions:", content)
        self.assertIn("## Discussion\n\n- **d8vjork**", content)
        self.assertIn("## Comments\n\n- **benface** [→](https://github.com/tailwindlabs/tailwindcss/discussions/307"
                      "#discussioncomment-55955) (2019-01-02, 1 upvote): ", content)

    def test_replies_and_the_answer(self):
        key = next(k for k in DISCUSSION if k.startswith("graphql:"))
        data = json.loads(json.dumps(DISCUSSION[key]))
        d = data["repository"]["discussion"]
        first = d["comments"]["nodes"][0]
        first["isAnswer"] = True
        first["replies"] = {"totalCount": 1, "nodes": [{"id": "R1", "url": "https://github.com/t/t/discussions/307#r1",
                                                        "body": "Thanks!", "createdAt": "2019-01-03T00:00:00Z",
                                                        "upvoteCount": 0, "author": {"login": "adamwathan"}}]}
        d["answer"] = {"id": first["id"]}
        gh = FakeGitHub({key: data})
        with mock.patch.object(thread, "log"):
            t = thread.fetch_discussion(gh, {"repo": "tailwindlabs/tailwindcss", "number": 307})
        self.assertEqual([c["author"] for c in t["comments"][:2]], ["benface", "adamwathan"])
        self.assertEqual(t["comments"][0]["notes"], ["the answer", "1 upvote"])
        self.assertEqual(t["comments"][1]["notes"], ["reply to benface"])
        self.assertTrue(t["facts"]["answered"])

    def test_missing_discussion(self):
        key = next(k for k in DISCUSSION if k.startswith("graphql:"))
        gh = FakeGitHub({key: {"repository": {"discussion": None}}})
        with self.assertRaisesRegex(NotFound, "no discussion #307"):
            thread.fetch_discussion(gh, {"repo": "tailwindlabs/tailwindcss", "number": 307})


class TestRelated(Base):
    def folder(self, topics):
        folder = self.root / "repos" / "github" / "kepano" / "defuddle"
        folder.mkdir(parents=True)
        write_json(folder / "metadata.json", {"source": "github", "id": REPO, "extras": {"topics": topics}})
        return folder

    def test_ranked_by_rare_shared_topics_then_stars_self_skipped(self):
        topics = load("repo.json")["topics"]
        gh = FakeGitHub(load("search.api.json"))
        known = self.root / "repos" / "github" / "danburzo" / "percollate"
        known.mkdir(parents=True)
        write_json(known / "metadata.json", {"source": "github", "id": "danburzo/percollate"})
        (known / "summary.html").write_text("x")
        folder = self.folder(topics)
        with mock.patch.object(related, "log"):
            found = related.similar(gh, REPO, topics, "html to markdown readability", 50, self.root, folder)
        searched = sorted(c.split("?q=")[1].split("&")[0] for c in gh.calls)
        self.assertEqual(searched, ["html+to+markdown+readability", "topic%3Acli", "topic%3Ahtml", "topic%3Amarkdown",
                                    "topic%3Amd", "topic%3Aobsidian", "topic%3Areadability"])  # not its own name
        self.assertNotIn(REPO, [f["repo"] for f in found])
        keys = [(-f["score"], -f["stars"]) for f in found]
        self.assertEqual(keys, sorted(keys))
        percollate = next(f for f in found if f["repo"] == "danburzo/percollate")
        self.assertEqual(percollate["summary"], "../../danburzo/percollate/summary.html")
        # readability (762 repos) weighs more than html (366k): 4 shared topics, yet html + cli count little
        self.assertEqual(found[0], percollate)
        trafilatura = next(f for f in found if f["repo"] == "adbar/trafilatura")
        self.assertGreater(trafilatura["score"], next(f for f in found if f["shared_topics"] == ["cli"])["score"])

    def test_the_library_is_walked_once_and_aliases_count(self):
        topics = load("repo.json")["topics"]
        known = self.root / "repos" / "github" / "adbar" / "trafilatura"
        known.mkdir(parents=True)
        write_json(known / "metadata.json", {"source": "github", "id": "adbar/Trafilatura-old",
                                             "extras": {"aliases": ["adbar/trafilatura"]}})
        (known / "summary.html").write_text("x")
        folder = self.folder(topics)
        with mock.patch.object(related, "log"), \
                mock.patch.object(related, "library_repos", wraps=related.library_repos) as walk:
            found = related.similar(FakeGitHub(load("search.api.json")), REPO, topics, None, 50, self.root, folder)
        walk.assert_called_once()
        self.assertGreater(len(found), 5)
        hit = next(f for f in found if f["repo"] == "adbar/trafilatura")
        self.assertEqual(hit["summary"], "../../adbar/trafilatura/summary.html")

    def test_no_topics_needs_a_query(self):
        folder = self.folder([])
        with mock.patch.object(related, "GitHub", return_value=FakeGitHub({})), \
                self.assertRaisesRegex(SkillError, "pass --query"):
            related.main([str(folder)])


if __name__ == "__main__":
    unittest.main()

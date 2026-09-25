#!/usr/bin/env python3
"""Unit tests for github/prepare.py (offline: recorded API answers for kepano/defuddle, repomix mocked)."""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import prepare  # noqa: E402  (github/prepare.py: this folder comes first)
from _common import CONTRACT_KEYS, ENVELOPE_KEYS, MissingTool, SkillError, read_json  # noqa: E402
from fake_github import FIXTURES, REPO, SHA, FakeGitHub, load, repo_answers  # noqa: E402

AGENTS = (FIXTURES / "AGENTS.md").read_text(encoding="utf-8")
PATHS = [t["path"] for t in load("tree.json")["tree"] if t["type"] == "blob"]


class TestPicking(unittest.TestCase):
    def test_docs_skip_tests_and_changelog_root_first(self):
        paths = ["README.md", "CHANGELOG.md", "AGENTS.md", "docs/index.md", "docs/deep/api.md", "docs/a.md",
                 "tests/expected/x.md", "website/README.md", "src/core.ts"]
        self.assertEqual(prepare.doc_paths(paths, "README.md"),
                         ["docs/index.md", "AGENTS.md", "docs/a.md", "docs/deep/api.md"])

    def test_focus_path_comes_first(self):
        paths = ["AGENTS.md", "docs/index.md", "website/README.md", "website/guide.md"]
        self.assertEqual(prepare.doc_paths(paths, "README.md", "website")[:2], ["website/README.md", "website/guide.md"])

    def test_deep_index_files_do_not_jump_ahead_of_root_docs(self):
        paths = ["docs/guides/advanced/README.md", "ARCHITECTURE.md", "docs/README.md", "docs/a.md"]
        self.assertEqual(prepare.doc_paths(paths, "README.md"),
                         ["docs/README.md", "ARCHITECTURE.md", "docs/a.md", "docs/guides/advanced/README.md"])

    def test_focus_is_a_whole_path_segment(self):
        paths = ["website/guide.md", "website2/notes.md", "websites.md"]
        self.assertEqual(prepare.doc_paths(paths, "README.md", "website/"), ["website/guide.md", "websites.md"])

    def test_focus_folder_markdown_even_under_tests(self):
        paths = ["tests/README.md", "tests/cases/a.md", "tests/x.py", "tests-other/b.md"]
        self.assertEqual(prepare.doc_paths(paths, "README.md", "tests"), ["tests/README.md", "tests/cases/a.md"])

    def test_focus_file_of_any_kind_comes_first(self):
        paths = ["AGENTS.md", "docs/index.md", "src/core.ts", "tests/fixtures/page.html"]
        self.assertEqual(prepare.doc_paths(paths, "README.md", "src/core.ts", focus_file=True)[0], "src/core.ts")
        self.assertEqual(prepare.doc_paths(paths, "README.md", "tests/fixtures/page.html", focus_file=True)[0],
                         "tests/fixtures/page.html")
        # a file the (cut) tree listing misses is still read
        self.assertEqual(prepare.doc_paths([], "README.md", "src/deep/x.go", focus_file=True), ["src/deep/x.go"])

    def test_code_file_is_numbered_in_a_fence(self):
        out = prepare.code_file("def f():\n    return 1\n", REPO, SHA, "src/a.py")
        blob = f"https://github.com/{REPO}/blob/{SHA}/src/a.py"
        self.assertEqual(out, f"[source]({blob}) · link line n as `[L<n>]({blob}#L<n>)`\n\n~~~python\n"
                              "1  def f():\n2      return 1\n~~~")


class TestFetchDocs(unittest.TestCase):
    def test_stops_after_consecutive_failures(self):
        gh = FakeGitHub({})  # every file 404s, as for a private repo read without access
        with mock.patch.object(prepare, "log"):
            docs = prepare.fetch_docs(gh, REPO, SHA, [f"docs/{i}.md" for i in range(2000)])
        self.assertEqual((docs, len(gh.calls)), ([], prepare.DOC_FAILS))

    def test_a_success_resets_the_failure_count_and_the_tries_are_capped(self):
        paths = [f"docs/{i}.md" for i in range(2000)]
        gh = FakeGitHub({}, {p: "x" for p in paths[1::2]})  # every other file exists
        with mock.patch.object(prepare, "log"):
            docs = prepare.fetch_docs(gh, REPO, SHA, paths)
        self.assertEqual((len(gh.calls), len(docs)), (prepare.DOC_TRIES, prepare.DOC_TRIES // 2))

    def test_binary_files_are_skipped(self):
        gh = FakeGitHub({}, {"a.png": "\x89PNG\x00\x00", "b.md": "ok"})
        with mock.patch.object(prepare, "log"):
            self.assertEqual(prepare.fetch_docs(gh, REPO, SHA, ["a.png", "b.md"]), [("b.md", "ok", "")])


class TestRef(unittest.TestCase):
    def gh(self, heads=(), tags=()):
        return FakeGitHub({f"repos/{REPO}/git/matching-refs/heads/feature": [{"ref": f"refs/heads/{h}"} for h in heads],
                           f"repos/{REPO}/git/matching-refs/tags/feature": [{"ref": f"refs/tags/{t}"} for t in tags]})

    def test_slashed_branch_is_the_longest_matching_ref(self):
        gh = self.gh(heads=["feature", "feature-x", "feature/x"])
        self.assertEqual(prepare.resolve_ref(gh, REPO, "feature/x/docs/a.md"), ("feature/x", "docs/a.md"))
        self.assertEqual(prepare.resolve_ref(gh, REPO, "feature/x"), ("feature/x", None))

    def test_tag_and_unknown_ref(self):
        self.assertEqual(prepare.resolve_ref(self.gh(tags=["feature/v1"]), REPO, "feature/v1/docs"),
                         ("feature/v1", "docs"))
        self.assertEqual(prepare.resolve_ref(self.gh(), REPO, "feature/docs"), ("feature", "docs"))  # a sha, say

    def test_a_single_segment_needs_no_lookup(self):
        gh = self.gh()
        self.assertEqual(prepare.resolve_ref(gh, REPO, "v1.0"), ("v1.0", None))
        self.assertEqual(gh.calls, [])


class TestTree(unittest.TestCase):
    def test_tree_keeps_shallow_paths(self):
        shown, more = prepare.shown_tree(["a/b/c/d.py", "z.md", "a/x.py", "b.md"], limit=3)
        self.assertEqual((shown, more), (["a/x.py", "b.md", "z.md"], 1))

    def test_language_share(self):
        self.assertEqual(prepare.language_share(load("languages.json")), ["TypeScript 96%", "SCSS 4%"])

    def test_cut_at_a_line_end_with_a_note(self):
        self.assertEqual(prepare.cut("one\ntwo\nthree", 9), ("one\ntwo", "*[cut: 6 more characters in the file]*"))
        self.assertEqual(prepare.cut("short", 9), ("short", ""))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        env = mock.patch.dict(os.environ, {"TELL_ME_ROOT": self.tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(self.tmp.cleanup)
        self.gh = FakeGitHub(repo_answers(), {"AGENTS.md": AGENTS})

    def run_main(self, *args, pack=None):
        out = io.StringIO()
        with mock.patch.object(prepare, "GitHub", return_value=self.gh), mock.patch.object(prepare, "log"), \
                mock.patch("subprocess.run", pack or mock.MagicMock()), redirect_stdout(out):
            self.assertEqual(prepare.main(list(args)), 0)
        return json.loads(out.getvalue())


class TestRepo(Base):
    def test_folder_content_and_contract(self):
        env = self.run_main(f"https://github.com/{REPO}")
        folder = self.root / "repos" / "github" / "kepano" / "defuddle"
        self.assertEqual((env["dir"], env["source"], env["kind"], env["files"]), (str(folder), "github", "repo",
                                                                                 len(PATHS)))
        self.assertTrue(set(ENVELOPE_KEYS) <= set(env))
        meta = read_json(folder / "metadata.json")
        self.assertTrue(set(CONTRACT_KEYS) <= set(meta))
        ex = meta["extras"]
        self.assertEqual((meta["id"], meta["author"], ex["license"], ex["release"]["tag"], ex["sha"]),
                         (REPO, "kepano", "MIT", "0.19.4", SHA))
        self.assertEqual(ex["docs"], ["AGENTS.md"])
        content = (folder / "content.md").read_text()
        blob = f"https://github.com/{REPO}/blob/{SHA}"
        self.assertIn("- languages: TypeScript 96%, SCSS 4%", content)
        self.assertIn("- latest release: 0.19.4 (2026-09-17)", content)
        self.assertIn(f"- commit: main @ {SHA[:12]} (2026-09-20)", content)
        self.assertIn(f"## README (README.md)\n\n> [L1]({blob}/README.md?plain=1#L1) de·", content)
        self.assertIn(f"[L6]({blob}/README.md?plain=1#L6) Defuddle extracts the main content", content)
        self.assertIn("## Files\n\n```\n", content)
        self.assertIn(f"## Docs\n\n### AGENTS.md\n\n#### Defuddle [#]({blob}/AGENTS.md#defuddle)", content)

    def test_rerun_reuses_refresh_refetches(self):
        first = self.run_main(f"https://github.com/{REPO}")
        calls = len(self.gh.calls)
        again = self.run_main(f"https://github.com/{REPO}")
        self.assertEqual((again["dir"], again["reused"], len(self.gh.calls)), (first["dir"], True, calls))
        fresh = self.run_main(f"https://github.com/{REPO}", "--refresh")
        self.assertEqual((fresh["dir"], fresh["reused"]), (first["dir"], True))
        self.assertGreater(len(self.gh.calls), calls)

    def test_url_case_is_canonicalized_and_kept_as_alias(self):
        self.gh.answers["repos/Kepano/Defuddle"] = self.gh.answers[f"repos/{REPO}"]
        env = self.run_main("https://github.com/Kepano/Defuddle")
        self.assertEqual(env["id"], REPO)
        self.assertEqual(read_json(Path(env["dir"]) / "metadata.json")["extras"]["aliases"], ["Kepano/Defuddle"])
        again = self.run_main("https://github.com/Kepano/Defuddle")
        self.assertEqual((again["dir"], again["reused"]), (env["dir"], True))

    def test_a_folder_link_is_the_repo_with_that_path_first(self):
        self.gh.files["website/README.md"] = "# Site\n\nThe docs site."
        env = self.run_main(f"https://github.com/{REPO}/tree/main/website")
        meta = read_json(Path(env["dir"]) / "metadata.json")
        self.assertEqual((env["kind"], meta["extras"]["focus_path"]), ("repo", "website"))
        self.assertEqual(meta["extras"]["docs"], ["website/README.md", "AGENTS.md"])
        self.assertIn("- focus: website", Path(env["content_file"]).read_text())

    def test_a_code_file_link_reads_that_file(self):
        self.gh.files["src/cli.ts"] = "#!/usr/bin/env node\nimport { x } from './x';\n"
        env = self.run_main(f"https://github.com/{REPO}/blob/main/src/cli.ts")
        meta = read_json(Path(env["dir"]) / "metadata.json")
        self.assertEqual((meta["extras"]["focus_path"], meta["extras"]["docs"][0]), ("src/cli.ts", "src/cli.ts"))
        content = Path(env["content_file"]).read_text()
        self.assertIn(f"### src/cli.ts\n\n[source](https://github.com/{REPO}/blob/{SHA}/src/cli.ts)", content)
        self.assertIn("~~~typescript\n1  #!/usr/bin/env node\n2  import { x } from './x';\n~~~", content)

    def tag(self, tag="0.18.0", sha="a" * 40):
        """A tag at another commit, with its own tree and README."""
        self.gh.answers |= {
            f"repos/{REPO}/git/matching-refs/tags/{tag}": [{"ref": f"refs/tags/{tag}"}],
            f"repos/{REPO}/commits/{tag}": {"sha": sha, "commit": {"committer": {"date": "2026-01-02T00:00:00Z"}}},
            f"repos/{REPO}/git/trees/{sha}?recursive=1": {"tree": [{"path": "docs/old.md", "type": "blob"},
                                                                   {"path": "README.md", "type": "blob"}]},
            f"repos/{REPO}/readme?ref={sha}": self.gh.answers[f"repos/{REPO}/readme?ref={SHA}"]}
        self.gh.files["docs/old.md"] = "Old docs."
        return sha

    def test_a_tag_link_reads_that_tag(self):
        old = self.tag()
        env = self.run_main(f"https://github.com/{REPO}/tree/0.18.0/docs")
        ex = read_json(Path(env["dir"]) / "metadata.json")["extras"]
        self.assertEqual((ex["sha"], ex["ref"], ex["focus_path"], ex["docs"]), (old, "0.18.0", "docs", ["docs/old.md"]))
        content = Path(env["content_file"]).read_text()
        self.assertIn(f"- commit: 0.18.0 @ {old[:12]} (2026-01-02), the link's ref; default branch main", content)
        self.assertIn(f"https://github.com/{REPO}/blob/{old}/docs/old.md?plain=1#L1", content)
        self.assertNotIn(SHA, content)
        again = self.run_main(f"https://github.com/{REPO}/tree/0.18.0/docs")
        self.assertTrue(again["reused"])
        main = self.run_main(f"https://github.com/{REPO}")  # another ref: refetched at the default branch
        self.assertEqual(read_json(Path(main["dir"]) / "metadata.json")["extras"]["sha"], SHA)

    def test_an_unknown_ref_is_an_error(self):
        with self.assertRaisesRegex(SkillError, "has no branch, tag or commit 'nope'"):
            self.run_main(f"https://github.com/{REPO}/tree/nope")

    def test_no_release_and_no_readme(self):
        del self.gh.answers[f"repos/{REPO}/releases/latest"], self.gh.answers[f"repos/{REPO}/readme?ref={SHA}"]
        content = Path(self.run_main(f"https://github.com/{REPO}")["content_file"]).read_text()
        self.assertIn("## README\n\n*No README.*", content)
        self.assertNotIn("latest release", content)

    def test_missing_repo_is_an_error(self):
        with self.assertRaisesRegex(SkillError, "not found on GitHub"), mock.patch.object(prepare, "log"), \
                mock.patch.object(prepare, "GitHub", return_value=self.gh):
            prepare.main(["https://github.com/kepano/nope"])

    def test_other_source_is_refused(self):
        with self.assertRaisesRegex(SkillError, "is a web input"):
            prepare.main(["https://example.com/post"])


class TestDeep(Base):
    def packer(self, words=5):
        def run(cmd, **kw):
            Path(cmd[cmd.index("-o") + 1]).write_text("pack " * words)
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return mock.MagicMock(side_effect=run)

    def test_deep_packs_the_repo_with_pinned_repomix(self):
        pack = self.packer()
        with mock.patch("shutil.which", return_value="/bin/npx"):
            env = self.run_main(f"https://github.com/{REPO}", "--deep", pack=pack)
        cmd = pack.call_args[0][0]
        self.assertEqual(cmd[:5], ["npx", "-y", prepare.REPOMIX, "--remote", f"https://github.com/{REPO}"])
        self.assertEqual((Path(env["pack_file"]).name, env["pack_words"]), ("repo-pack.md", 5))
        self.assertEqual(cmd[5:7], ["--remote-branch", SHA])  # the commit the anchors point at
        self.assertIn(f"- repo pack: repo-pack.md (5 words, commit {SHA[:12]})", Path(env["content_file"]).read_text())

    def test_deep_after_a_plain_run_refetches_then_reuses(self):
        self.run_main(f"https://github.com/{REPO}")
        with mock.patch("shutil.which", return_value="/bin/npx"):
            env = self.run_main(f"https://github.com/{REPO}", "--deep", pack=self.packer())
            again = self.run_main(f"https://github.com/{REPO}", "--deep", pack=self.packer(9))
        self.assertEqual((again["reused"], again["pack_words"]), (True, 5))
        self.assertTrue(env["pack_file"])

    def test_refresh_without_deep_drops_a_pack_of_another_commit(self):
        with mock.patch("shutil.which", return_value="/bin/npx"):
            env = self.run_main(f"https://github.com/{REPO}", "--deep", pack=self.packer())
        same = self.run_main(f"https://github.com/{REPO}", "--refresh")  # same commit: the pack still fits
        self.assertEqual(same["pack_file"], env["pack_file"])
        self.gh.answers[f"repos/{REPO}/commits/main"] = {"sha": "b" * 40}
        self.gh.answers[f"repos/{REPO}/git/trees/{'b' * 40}?recursive=1"] = load("tree.json")
        fresh = self.run_main(f"https://github.com/{REPO}", "--refresh")
        ex = read_json(Path(fresh["dir"]) / "metadata.json")["extras"]
        self.assertIsNone(fresh["pack_file"])
        self.assertFalse({"pack_file", "pack_words", "pack_sha"} & set(ex))
        self.assertFalse(Path(env["pack_file"]).exists())
        self.assertNotIn("repo pack", Path(fresh["content_file"]).read_text())

    def test_deep_without_npx_is_a_missing_tool(self):
        with mock.patch("shutil.which", return_value=None), self.assertRaisesRegex(MissingTool, "npx"):
            self.run_main(f"https://github.com/{REPO}", "--deep")

    def test_repomix_failure_says_to_go_without_deep(self):
        fail = mock.MagicMock(return_value=subprocess.CompletedProcess([], 1, "", "Error: clone failed"))
        with mock.patch("shutil.which", return_value="/bin/npx"), \
                self.assertRaisesRegex(SkillError, "repomix failed: Error: clone failed; summarize without --deep"):
            self.run_main(f"https://github.com/{REPO}", "--deep", pack=fail)


if __name__ == "__main__":
    unittest.main()

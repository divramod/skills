"""Tests for hooks.py and the managed dispatcher (templates/hooks/merge-to-main/lib.sh).

    python3 -m unittest discover -s skills/mtm/scripts
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hooks  # type: ignore[import-not-found]  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "hooks.py"

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
}


def sh(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, env={**os.environ, **GIT_ENV}, capture_output=True, text=True,
                          check=check)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class Repo(unittest.TestCase):
    """origin (bare) <- main checkout on main, plus a worktree on branch `wt`."""

    def setUp(self) -> None:
        os.environ.update(GIT_ENV)
        self.tmp = Path(tempfile.mkdtemp())
        self.origin = self.tmp / "origin.git"
        self.main = self.tmp / "repo"
        self.wt = self.tmp / "wt"
        sh(["git", "init", "--quiet", "--bare", "-b", "main", str(self.origin)], self.tmp)
        sh(["git", "clone", "--quiet", str(self.origin), str(self.main)], self.tmp)
        write(self.main / "code/rust/Cargo.toml", "[workspace]\nmembers = ['apps/*']\n")
        write(self.main / "code/rust/apps/cli/Cargo.toml", "[package]\nname = 'cli'\n")
        write(self.main / "code/rust/apps/cli/src/main.rs", "fn main() {}\n")
        write(self.main / "code/typescript/apps/web/package.json", '{"scripts": {"test": "x", "lint": "y"}}')
        write(self.main / "code/typescript/apps/web/bun.lock", "")
        write(self.main / "code/typescript/apps/web/src/index.js", "1\n")
        self.commit(self.main, "init")
        sh(["git", "push", "--quiet", "-u", "origin", "main"], self.main)
        sh(["git", "remote", "set-head", "origin", "main"], self.main)
        sh(["git", "worktree", "add", "--quiet", "-b", "wt", str(self.wt)], self.main)

    def tearDown(self) -> None:
        sh(["rm", "-rf", str(self.tmp)], Path("/"))

    def commit(self, cwd: Path, msg: str) -> None:
        sh(["git", "add", "-A"], cwd)
        sh(["git", "commit", "--quiet", "-m", msg], cwd)

    def run_py(self, *args: str) -> tuple[int, Any]:
        out = io.StringIO()
        with redirect_stdout(out):
            code = hooks.main([*args])
        text = out.getvalue()
        try:
            return code, json.loads(text)
        except json.JSONDecodeError:
            return code, text

    def part(self, repo: Path, name: str, paths: str, **phases: str) -> None:
        d = repo / hooks.HOOKS / "parts" / name
        write(d / "paths", paths)
        for phase, body in phases.items():
            write(d / f"{phase.replace('_', '-')}.sh", body)

    def try_phase(self, phase: str, *extra: str) -> subprocess.CompletedProcess:
        return sh([sys.executable, str(SCRIPT), "try", phase, "--repo", str(self.wt), *extra],
                  self.wt, check=False)


class InitTest(Repo):
    def test_init_creates_managed_files_and_is_idempotent(self) -> None:
        code, out = self.run_py("init", "--repo", str(self.wt))
        self.assertEqual(code, 0)
        self.assertEqual(set(out["files"].values()), {"created"})
        for name in ("lib.sh", *(f"{p}.sh" for p in hooks.PHASES)):
            self.assertTrue((self.wt / hooks.HOOKS / name).is_file())
        code, out = self.run_py("init", "--repo", str(self.wt))
        self.assertEqual(set(out["files"].values()), {"unchanged"})

    def test_init_refuses_an_unmanaged_hook_unless_forced(self) -> None:
        write(self.wt / hooks.HOOKS / "main-pre-commit.sh", "echo mine\n")
        code, out = self.run_py("init", "--repo", str(self.wt))
        self.assertEqual(code, 1)
        self.assertTrue(out["files"]["main-pre-commit.sh"].startswith("conflict"))
        self.assertEqual((self.wt / hooks.HOOKS / "main-pre-commit.sh").read_text(), "echo mine\n")
        code, out = self.run_py("init", "--repo", str(self.wt), "--force")
        self.assertEqual((code, out["files"]["main-pre-commit.sh"]), (0, "replaced"))


class AppsTest(Repo):
    def test_lists_apps_with_stack_workspace_and_parts(self) -> None:
        self.run_py("init", "--repo", str(self.wt))
        self.part(self.wt, "rust-workspace", ":(glob)code/rust/**\n", worktree_pre_merge="true\n")
        code, out = self.run_py("apps", "--repo", str(self.wt))
        self.assertEqual(code, 0)
        self.assertTrue(out["managed"])
        units = {u["name"]: u for u in out["units"]}
        self.assertEqual(units["cli"]["stack"], ["cargo"])
        self.assertEqual(units["cli"]["workspace"], "code/rust")
        self.assertEqual(units["cli"]["parts"], ["rust-workspace"])
        self.assertEqual(units["web"]["stack"], ["node", "bun"])
        self.assertEqual(units["web"]["scripts"], ["lint", "test"])
        self.assertEqual(units["web"]["parts"], [])

    def test_excludes_apply_to_a_single_include(self) -> None:
        write(self.wt / "code/rust/apps/cli/README.md", "docs\n")
        self.commit(self.wt, "docs")
        specs = [":(glob)code/rust/**", ":(exclude,glob)**/*.md"]
        files = hooks.tracked(self.wt, specs)
        self.assertIn("code/rust/apps/cli/src/main.rs", files)
        self.assertNotIn("code/rust/apps/cli/README.md", files)
        self.assertEqual(hooks.tracked(self.wt, ["code/rust/", ":!**/*.rs", ":^**/*.md"]),
                         {"code/rust/Cargo.toml", "code/rust/apps/cli/Cargo.toml"})

    def test_a_repo_without_code_apps_is_one_app(self) -> None:
        sh(["git", "rm", "-rq", "code"], self.wt)
        self.commit(self.wt, "flat")
        _, out = self.run_py("apps", "--repo", str(self.wt))
        self.assertEqual([(u["name"], u["path"]) for u in out["units"]], [("wt", ".")])


class CheckTest(Repo):
    def test_reports_errors_and_warnings(self) -> None:
        self.run_py("init", "--repo", str(self.wt))
        self.part(self.wt, "good", ":(glob)code/rust/**\n", worktree_pre_merge="true\n")
        self.part(self.wt, "typo", "code/rsut/\n", main_pre_commit="true\n")
        self.part(self.wt, "broken", "code/rust/\n", main_post_commit="if then\n")
        write(self.wt / hooks.HOOKS / "parts/good/post-merge.sh", "true\n")
        code, out = self.run_py("check", "--repo", str(self.wt))
        self.assertEqual(code, 1)
        text = "\n".join(out["errors"])
        self.assertIn("`code/rsut/` matches no tracked file", text)
        self.assertIn("parts/broken/main-post-commit.sh", text)
        warnings = "\n".join(out["warnings"])
        self.assertIn("parts/good/post-merge.sh: not a phase script", warnings)
        self.assertIn("app code/typescript/apps/web is in no part's paths", warnings)

    def test_clean_hooks_pass(self) -> None:
        self.run_py("init", "--repo", str(self.wt))
        self.part(self.wt, "all", "code/\n", worktree_pre_merge="true\n")
        code, out = self.run_py("check", "--repo", str(self.wt))
        self.assertEqual((code, out["errors"], out["warnings"]), (0, [], []))


class DispatcherTest(Repo):
    """The phases through `hooks.py try`, which runs them the way hal2-cli-git does."""

    def setUp(self) -> None:
        super().setUp()
        self.run_py("init", "--repo", str(self.wt))
        self.log = self.tmp / "log"
        self.body = f'hal_skip_unless_changed\nhal_log ran\necho "$HAL_PHASE $HAL_PART $PWD" >> {self.log}\n'

    def ran(self) -> list[str]:
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_worktree_pre_merge_runs_only_changed_parts_in_the_worktree(self) -> None:
        self.part(self.wt, "rust", ":(glob)code/rust/**\n", worktree_pre_merge=self.body)
        self.part(self.wt, "web", ":(glob)code/typescript/**\n", worktree_pre_merge=self.body)
        write(self.wt / "code/rust/apps/cli/src/main.rs", "fn main() { }\n")
        self.commit(self.wt, "change rust")
        done = self.try_phase("worktree-pre-merge")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.ran(), [f"worktree-pre-merge rust {self.wt.resolve()}"])
        self.assertIn("worktree-pre-merge[web]: unchanged, skipped", done.stdout)

    def test_all_changed_and_only_part(self) -> None:
        self.part(self.wt, "rust", ":(glob)code/rust/**\n", worktree_pre_merge=self.body)
        self.part(self.wt, "web", ":(glob)code/typescript/**\n", worktree_pre_merge=self.body)
        self.commit(self.wt, "hooks")
        self.try_phase("worktree-pre-merge", "--all-changed", "--part", "web")
        self.assertEqual([line.split()[1] for line in self.ran()], ["web"])

    def test_a_failing_pre_part_stops_the_phase(self) -> None:
        self.part(self.wt, "a", "code/\n", worktree_pre_merge="exit 7\n")
        self.part(self.wt, "b", "code/\n", worktree_pre_merge=self.body)
        self.commit(self.wt, "hooks")
        done = self.try_phase("worktree-pre-merge", "--all-changed")
        self.assertEqual(done.returncode, 7)
        self.assertIn("worktree-pre-merge[a]: failed with exit code 7", done.stderr)
        self.assertEqual(self.ran(), [])

    def test_a_failing_post_part_does_not_stop_the_others(self) -> None:
        self.part(self.wt, "a", "code/\n", main_post_commit="false\n")
        self.part(self.wt, "b", "code/\n", main_post_commit=self.body)
        self.commit(self.wt, "hooks")
        done = self.try_phase("main-post-commit", "--all-changed", "--yes")
        self.assertEqual(done.returncode, 1)
        self.assertIn("main-post-commit: failed parts: a", done.stderr)
        self.assertEqual([line.split()[1] for line in self.ran()], ["b"])

    def test_main_post_commit_needs_yes(self) -> None:
        done = self.try_phase("main-post-commit")
        self.assertEqual(done.returncode, 1)
        self.assertIn("--yes", done.stderr)

    def test_main_pre_commit_sees_the_staged_merge_in_a_throwaway_worktree(self) -> None:
        self.part(self.wt, "rust", ":(glob)code/rust/**\n", main_pre_commit=self.body)
        self.part(self.wt, "web", ":(glob)code/typescript/**\n", main_pre_commit=self.body)
        write(self.wt / "code/typescript/apps/web/src/index.js", "2\n")
        self.commit(self.wt, "change web")
        done = self.try_phase("main-pre-commit")
        self.assertEqual(done.returncode, 0, done.stderr)
        [line] = self.ran()
        phase, part, cwd = line.split()
        self.assertEqual((phase, part), ("main-pre-commit", "web"))
        self.assertNotIn(str(self.main), cwd)
        self.assertFalse(Path(cwd).exists(), "the throwaway worktree is removed")
        self.assertEqual(sh(["git", "status", "--porcelain"], self.main).stdout, "")

    def test_uncommitted_hook_edits_are_tried(self) -> None:
        self.part(self.wt, "web", ":(glob)code/typescript/**\n", main_post_commit=self.body)
        done = self.try_phase("main-post-commit", "--all-changed", "--yes")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual([line.split()[1] for line in self.ran()], ["web"])

    def test_changed_since_and_extra_pathspecs(self) -> None:
        first = sh(["git", "rev-parse", "HEAD"], self.wt).stdout.strip()
        body = (f'if hal_changed_since {first} ":(exclude,glob)**/*.md"; then r=yes; else r=no; fi\n'
                f'echo "$r" >> {self.log}\n')
        self.part(self.wt, "rust", ":(glob)code/rust/**\n", main_post_commit=body)
        write(self.wt / "code/rust/README.md", "docs\n")
        self.commit(self.wt, "docs only")
        self.try_phase("main-post-commit", "--yes")
        write(self.wt / "code/rust/apps/cli/src/main.rs", "fn main() { }\n")
        self.commit(self.wt, "code")
        self.try_phase("main-post-commit", "--yes")
        self.assertEqual(self.ran(), ["no", "yes"])

    def test_a_part_without_paths_fails(self) -> None:
        write(self.wt / hooks.HOOKS / "parts/nopaths/worktree-pre-merge.sh", "hal_skip_unless_changed\n")
        self.commit(self.wt, "hooks")
        done = self.try_phase("worktree-pre-merge")
        self.assertEqual(done.returncode, 2)
        self.assertIn("no paths file", done.stderr)


if __name__ == "__main__":
    unittest.main()

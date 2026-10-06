#!/usr/bin/env python3
"""Tests for create.py with fake hal2 CLIs and a fake login shell on PATH (offline: no agent is started)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent

FAKE = r'''#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps([os.path.basename(sys.argv[0])] + sys.argv[1:] + ["TMUX=" + os.environ.get("TMUX", "")]) + "\n")
args, repo = sys.argv[1:], os.environ["FAKE_REPO"]
name = os.path.basename(repo)
if args[:1] == ["list"]:
    print(json.dumps([{"pane_id": "%1", "slot": "01", "state": "idle", "project": repo},
                      {"pane_id": "%2", "slot": "05", "state": "ended", "project": repo}]))
elif args[:2] == ["terminal", "list"]:
    print(json.dumps([{"worktree": "/wt/" + name + "/02", "alive": True},
                      {"worktree": "/wt/" + name + "/03", "alive": False}]))
elif args[:2] == ["worktree", "list"]:
    w = lambda n, **k: {"name": n, "path": "/wt/" + n, **k}
    extra = [{"name": n, "path": os.path.join(os.environ["FAKE_WT"], n)}
             for n in os.environ.get("FAKE_EXTRA", "").split(",") if n]
    print(json.dumps({"worktrees": [{"name": "main", "main": True}, w("01"), w("02"),
        w("03", plan="0085-old"), w("04", main_ahead=3), w("05", dirty=True), w("06", main_behind=400),
        w("07")] + extra}))
elif args[:2] == ["worktree", "queue"]:
    print(json.dumps({"queue": [{"repo": name, "slot": "07", "state": "held"}]}))
elif args[:2] == ["worktree", "run"]:
    print("setup ...")
    path = "/wt/" + args[2]
    if os.environ.get("FAKE_WT"):  # create the worktree like hal2's ensure: an existing branch is kept
        import subprocess
        path = os.path.join(os.environ["FAKE_WT"], args[2])
        if not os.path.isdir(path):
            has = subprocess.run(["git", "rev-parse", "--verify", "--quiet", "refs/heads/" + args[2]], cwd=repo,
                                 capture_output=True).returncode == 0
            subprocess.run(["git", "worktree", "add", "-q", path] + ([args[2]] if has else ["-b", args[2]]),
                           cwd=repo, check=True)
    print(json.dumps({"mode": "terminal", "pane": "t:abc", "slot": args[2], "worktree": path}))
'''

SHELL = '#!/bin/sh\n# a login shell without the login: runs the command it gets with -lc\nexec /bin/sh -c "$2"\n'


class TestCreate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.repo = t / "app"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        self.bin = t / "bin"
        self.bin.mkdir()
        for name in ("hal2-cli-agents", "hal2-cli-git"):
            (self.bin / name).write_text(FAKE)
            (self.bin / name).chmod(0o755)
        (self.bin / "fakeshell").write_text(SHELL)
        (self.bin / "fakeshell").chmod(0o755)
        self.log = t / "log"
        self.wt = t / "wt"
        self.wt.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def run_create(self, *args, extra="") -> dict:
        r = self.run_raw(*args, extra=extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def refused(self, *args, extra="") -> str:
        r = self.run_raw(*args, extra=extra)
        self.assertEqual(r.returncode, 1, r.stdout)
        return r.stderr

    def run_raw(self, *args, extra="") -> subprocess.CompletedProcess:
        env = dict(os.environ, PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}", FAKE_LOG=str(self.log),
                   FAKE_REPO=str(self.repo.resolve()), SHELL=str(self.bin / "fakeshell"), TMUX="/tmp/x,1,0",
                   FAKE_WT=str(self.wt), FAKE_EXTRA=extra)
        return subprocess.run([sys.executable, str(HERE / "create.py"), "--repo", str(self.repo), *args],
                              capture_output=True, text=True, env=env)

    def run_call(self):
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        return next(c for c in calls if c[1:3] == ["worktree", "run"])

    def test_the_first_slot_without_session_and_without_work(self):
        out = self.run_create()
        self.assertEqual((out["slot"], out["pane"], out["attach"]), ("06", "t:abc", "hal2-cli-agents attach app/06"))
        self.assertEqual([(s["slot"], s["why"]) for s in out["skipped"]],
                         [("03", "works on 0085-old"), ("04", "3 commits not on main"), ("05", "uncommitted changes")])
        run = self.run_call()
        self.assertEqual(run[3:7], ["06", "--agent", "claude", "--detach"])
        self.assertEqual(run[-1], "TMUX=")  # started outside this tmux pane
        self.assertEqual(run[run.index("--prompt") + 1], "/mfm")

    def test_a_prompt_runs_after_mfm_unless_exact_and_flags_pass_through(self):
        self.run_create("--prompt", "/shoot 13", "--model", "m1", "--tmux")
        run = self.run_call()
        self.assertEqual(run[run.index("--prompt") + 1], "Run /mfm (merge-from-main) first, then:\n\n/shoot 13")
        self.assertEqual(run[run.index("--model") + 1], "m1")
        self.assertIn("--tmux", run)
        self.log.unlink()
        self.run_create("--prompt", "the shot", "--exact")
        run = self.run_call()
        self.assertEqual(run[run.index("--prompt") + 1], "the shot")

    # a parallel plan's subservant (skills plan 0013)

    def git(self, *args, cwd=None) -> str:
        return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd or self.repo,
                              capture_output=True, text=True, check=True).stdout.strip()

    def with_origin(self) -> str:
        """main and branch 02 (one commit ahead) on a bare origin; the sha of origin/02."""
        origin = Path(self.tmp.name) / "origin.git"
        self.git("init", "-q", "--bare", "-b", "main", str(origin))
        self.git("commit", "-q", "--allow-empty", "-m", "main")
        self.git("branch", "-M", "main")
        self.git("remote", "add", "origin", str(origin))
        self.git("push", "-q", "-u", "origin", "main")
        self.git("checkout", "-q", "-b", "02")
        self.git("commit", "-q", "--allow-empty", "-m", "lead work")
        self.git("push", "-q", "origin", "02")
        self.git("checkout", "-q", "main")
        self.git("branch", "-D", "02")
        self.git("remote", "set-head", "origin", "main")
        return self.git("rev-parse", "origin/02")

    def test_from_starts_the_search_at_the_slot(self):
        out = self.run_create("--from", "30")
        self.assertEqual((out["slot"], out["skipped"]), ("30", []))
        self.assertIn("--from needs a slot from 01 to 99", self.refused("--from", "0"))

    def test_a_subservant_slot_branches_from_base_with_the_marker(self):
        sha = self.with_origin()

        out = self.run_create("--from", "30", "--base", "origin/02", "--lead", "02 0005-big 3", "--prompt", "brief")

        slot = self.wt / "30"
        self.assertEqual((out["slot"], out["base"], out["lead"]), ("30", "origin/02", "02 0005-big 3"))
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=slot), sha)
        self.assertEqual((slot / "plans" / "LEAD").read_text(), "02 0005-big 3\n")
        self.assertEqual((slot / "plans" / "CURRENT_PLAN").read_text(), "0005-big\n")
        self.assertEqual(self.git("status", "--porcelain", cwd=slot), "")  # both ignored through info/exclude
        run = self.run_call()
        self.assertEqual(run[run.index("--prompt") + 1], "brief")  # --lead implies --exact: no /mfm

    def test_a_leftover_branch_with_own_commits_is_skipped(self):
        self.with_origin()
        self.git("checkout", "-q", "-b", "30")
        self.git("commit", "-q", "--allow-empty", "-m", "unlanded")
        self.git("checkout", "-q", "main")
        self.git("branch", "31", "main")  # a leftover whose commits are on main: free

        out = self.run_create("--from", "30", "--base", "origin/02")

        self.assertEqual(out["slot"], "31")
        self.assertEqual(out["skipped"], [{"slot": "30", "why": "branch 30 holds 1 commit in neither origin/02 nor main"}])
        self.assertEqual(self.git("rev-parse", "31"), self.git("rev-parse", "origin/02"))

    def test_a_reused_clean_slot_is_reset_to_base_and_marked_before_the_start(self):
        sha = self.with_origin()
        self.git("worktree", "add", "-q", "-b", "30", str(self.wt / "30"))

        out = self.run_create("--from", "30", "--base", "origin/02", "--lead", "02 0005-big 4", "--min-free-gb",
                              "999999999", extra="30")

        self.assertEqual(out["slot"], "30")
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.wt / "30"), sha)
        self.assertEqual((self.wt / "30" / "plans" / "LEAD").read_text(), "02 0005-big 4\n")

    def test_a_new_worktree_needs_free_disk(self):
        error = self.refused("--from", "30", "--min-free-gb", "999999999")

        self.assertIn("a new worktree needs 999999999 (--min-free-gb)", error)
        self.assertFalse(self.log.exists() and "run" in self.log.read_text())

    def test_a_bad_lead_is_refused(self):
        self.with_origin()
        self.git("worktree", "add", "-q", "-b", "30", str(self.wt / "30"))

        error = self.refused("--from", "30", "--lead", "02 0005-big", extra="30")

        self.assertIn("--lead needs '<lead-slot> <plan> <step>'", error)


if __name__ == "__main__":
    unittest.main()

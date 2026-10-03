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
    print(json.dumps({"worktrees": [{"name": "main", "main": True}, w("01"), w("02"),
        w("03", plan="0085-old"), w("04", main_ahead=3), w("05", dirty=True), w("06", main_behind=400),
        w("07")]}))
elif args[:2] == ["worktree", "queue"]:
    print(json.dumps({"queue": [{"repo": name, "slot": "07", "state": "held"}]}))
elif args[:2] == ["worktree", "run"]:
    print("setup ...")
    print(json.dumps({"mode": "terminal", "pane": "t:abc", "slot": args[2], "worktree": "/wt/" + args[2]}))
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

    def tearDown(self):
        self.tmp.cleanup()

    def run_create(self, *args, worktrees=None):
        env = dict(os.environ, PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}", FAKE_LOG=str(self.log),
                   FAKE_REPO=str(self.repo.resolve()), SHELL=str(self.bin / "fakeshell"), TMUX="/tmp/x,1,0")
        r = subprocess.run([sys.executable, str(HERE / "create.py"), "--repo", str(self.repo), *args],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

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


if __name__ == "__main__":
    unittest.main()

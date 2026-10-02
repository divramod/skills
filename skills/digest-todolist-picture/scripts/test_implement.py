#!/usr/bin/env python3
"""Tests for implement.py with fake hal2 CLIs on PATH (offline: no agent is started, nothing is typed)."""
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
log = os.environ["FAKE_LOG"]
with open(log, "a") as f:
    f.write(json.dumps([os.path.basename(sys.argv[0])] + sys.argv[1:]) + "\n")
args = sys.argv[1:]
repo = os.environ["FAKE_REPO"]
if args[:2] == ["shots", "list-open"]:
    print(json.dumps({"shots": [{"number": "4", "title": "tabs: sort button", "body": "A button that sorts tabs.",
                                 "path": repo + "/shotfiles/app.md"}]}))
elif args[:2] == ["shots", "mark-sent"]:
    print("{}")
elif args[:1] == ["list"]:
    print(json.dumps([{"pane_id": "%7", "slot": "03", "kind": "claude", "state": "working", "title": "t",
                       "project": repo}, {"pane_id": "%9", "slot": "01", "kind": "claude", "state": "idle",
                       "project": "/elsewhere"}]))
elif args[:1] == ["spawn"]:
    print(json.dumps({"project": repo, "slot": "05", "kind": "claude", "mode": "terminal", "pane": "t:abc",
                      "worktree": "/wt/05"}))
'''


class TestImplement(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.repo = t / "app"
        (self.repo / "shotfiles").mkdir(parents=True)
        (self.repo / "shotfiles" / "app.md").write_text("# app\n\n## shot 4 tabs: sort button\nA button that sorts tabs.\n")
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "remote", "add", "origin", "git@github.com:me/app.git"], check=True)
        self.bin = t / "bin"
        self.bin.mkdir()
        for name in ("hal2-cli-shooter", "hal2-cli-agents"):
            (self.bin / name).write_text(FAKE)
            (self.bin / name).chmod(0o755)
        self.log = t / "log"
        self.home = t / "home"
        self.home.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def run_imp(self, *args, ok=True):
        env = dict(os.environ, PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}", HOME=str(self.home),
                   FAKE_LOG=str(self.log), FAKE_REPO=str(self.repo.resolve()))
        r = subprocess.run([sys.executable, str(HERE / "implement.py"), *args], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode == 0, ok, r.stderr)
        return json.loads(r.stdout) if ok else r.stderr

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_new_worktree_gets_the_shot_prompt_then_the_shot_is_marked(self):
        out = self.run_imp("send", "--repo", str(self.repo), "--shotfile", "app", "--number", "4")
        self.assertEqual((out["mode"], out["slot"], out["remote_control"]), ("new", "05", "app-05"))
        spawn = next(c for c in self.calls() if c[1] == "spawn")
        prompt = spawn[spawn.index("--prompt") + 1]
        self.assertIn("# shot 4 tabs: sort button (app)\nA button that sorts tabs.", prompt)
        self.assertIn('This is shot 4 of the feature "app" in repo me/app.', prompt)
        self.assertIn("titled `app 4 tabs: sort button`", prompt)
        self.assertEqual(Path(out["bullet"]).read_text().strip(), prompt)
        mark = self.calls()[-1]
        self.assertEqual(mark[1:4] + mark[mark.index("--worktree"):mark.index("--worktree") + 2],
                         ["shots", "mark-sent", "app", "--worktree", "05"])

    def test_existing_session_gets_the_bullet_typed_in(self):
        out = self.run_imp("send", "--repo", str(self.repo), "--shotfile", "app", "--number", "4", "--pane", "%7")
        self.assertEqual((out["mode"], out["slot"], out["busy"]), ("existing", "03", True))
        sends = [c[2:] for c in self.calls() if c[1] == "send"]
        self.assertEqual(sends, [["%7", "C-u", "--key"], ["%7", "@" + out["bullet"]], ["%7", "enter", "--key"],
                                 ["%7", "enter", "--key"]])
        self.assertIn("03", self.calls()[-1])

    def test_sessions_only_lists_this_repo_and_unknown_pane_fails(self):
        self.assertEqual([s["pane_id"] for s in self.run_imp("sessions", "--repo", str(self.repo))], ["%7"])
        err = self.run_imp("send", "--repo", str(self.repo), "--shotfile", "app", "--number", "4", "--pane", "%9",
                           ok=False)
        self.assertIn("no live agent session %9", err)
        self.assertFalse(any(c[1] in ("send", "mark-sent") or c[1:3] == ["shots", "mark-sent"] for c in self.calls()))


if __name__ == "__main__":
    unittest.main()

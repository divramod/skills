"""decisions.py lists a checkout's decisions and builds the farmer's decision check (skills plan 0008)."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "decisions.py"
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
       "GIT_COMMITTER_EMAIL": "t@t"}
PLAN = """# Plan 0003: x

## Pre-authorized

- 2026-10-05 (the user, relayed by the farmer): deploy to staging. User: "go"

## Decisions

- 2026-10-04 (user): keep sqlite,
  no postgres.
- <decisions taken while planning or grilling, with dates>

## Notes

- not a decision
"""
HANDOFF = """# Handoff

Updated 2026-10-05, branch `04`, written at `abc1234`.
Farmer: farmer-a4 (hal2)

## Plan
[Plan 0003](plans/0003-x/plan.md): 1/3 done.

## Open
- which port the server uses (waiting for the farmer)
"""


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, env=ENV, text=True, capture_output=True, check=True).stdout


class DecisionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.main = Path(self.tmp.name) / "skills"
        self.main.mkdir()
        git(self.main, "init", "-q", "-b", "main")
        git(self.main, "commit", "-q", "--allow-empty", "-m", "init")
        self.slot = Path(self.tmp.name) / "wt" / "04"
        git(self.main, "worktree", "add", "-q", "-b", "04", str(self.slot))
        (self.slot / "plans" / "0003-x").mkdir(parents=True)
        (self.slot / "plans" / "0003-x" / "plan.md").write_text(PLAN)

    def tearDown(self):
        self.tmp.cleanup()

    def run_it(self, *args):
        p = subprocess.run(["python3", str(SCRIPT), "--json", *args], cwd=self.slot, env=ENV, text=True,
                           capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def test_the_handoff_names_the_farmer_of_another_repo(self):
        (self.slot / "HANDOFF.md").write_text(HANDOFF)
        r = self.run_it()
        self.assertEqual((r["plan"], r["farmer"], r["farmer_repo"], r["slot"]),
                         ("plans/0003-x/plan.md", "farmer-a4", "hal2", "skills/04"))
        self.assertEqual([d["text"] for d in r["decisions"]], [
            "2026-10-04 (user): keep sqlite, no postgres.",
            '2026-10-05 (the user, relayed by the farmer): deploy to staging. User: "go"',
            "which port the server uses (waiting for the farmer)"])
        self.assertEqual(r["message"], "decision check skills/04: I have these decisions: (1) 2026-10-04 (user): "
                                       "keep sqlite, no postgres. (2) 2026-10-05 (the user, relayed by the farmer): "
                                       'deploy to staging. User: "go" (3) which port the server uses (waiting for the '
                                       "farmer). Did I forget one?")

    def test_current_plan_and_no_farmer_mean_this_repos_farmer(self):
        (self.slot / "plans" / "CURRENT_PLAN").write_text("0003-x\n")
        r = self.run_it()
        self.assertEqual((r["plan"], r["farmer"], r["farmer_repo"], r["slot"]),
                         ("plans/0003-x/plan.md", None, "skills", "04"))
        self.assertTrue(r["message"].startswith("decision check 04: I have these decisions: (1) 2026-10-04"))

    def test_nothing_found(self):
        r = self.run_it("--farmer-repo", "skills")
        self.assertEqual((r["plan"], r["decisions"]), (None, []))
        self.assertEqual(r["message"], "decision check 04: I have these decisions: none. Did I forget one?")


if __name__ == "__main__":
    unittest.main()

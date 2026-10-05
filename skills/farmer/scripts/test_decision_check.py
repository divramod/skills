"""Skills plan 0008: a servant's `decision check <slot>` after its clear, answered as code from the farmer's log."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import decision_check as dc
import farmer
import mtm_scan
from test_farmer import Repo, git

BUMPS = {"at": "2026-10-05T21:30:00", "kind": "decision", "slot": "12",
         "what": "version bumps: conventional commits, dependents get a patch bump",
         "note": 'user: "every lib or app, which changed, should also be version bumped"'}
RUNS = {"at": "2026-10-05T21:41:34", "kind": "decision", "slot": "12",
        "what": "delete all old GitHub Actions workflow runs",
        "note": 'user: "it should delete all the old workflow runs"'}
HANDOFF = {"at": "2026-10-05T22:04:13", "kind": "decision", "slot": "-",
           "what": "handoff skill: after clear-and-continue a servant asks the farmer 'did I forget a decision?'; "
                   "built now by a servant in ~/a/skills (slot 04)",
           "note": 'user: "can we adapt the handoff" then "1"'}
OTHER = {"at": "2026-10-05T09:00:00", "kind": "decision", "slot": "07", "what": "use sqlite", "note": "x"}
LOG = [BUMPS, RUNS, HANDOFF, OTHER, {"at": "2026-10-05T10:00:00", "kind": "ask", "slot": "12", "what": "q"}]


def check(message, trees=("12", "04", "07")):
    return dc.check(message, "hal2", LOG, list(trees))


class Check(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())  # no real ~/.hal/git/worktree slot counts as known
        p = mock.patch.object(dc, "WORKTREES", self.root)
        p.start()
        self.addCleanup(p.stop)

    def test_a_missing_decision_comes_back_with_its_date_and_the_users_words(self):
        code, text, entry = check("decision check 12: I have these decisions: version bumps by conventional commits, "
                                  "dependents get a patch bump. Did I forget one?")
        self.assertEqual(code, 0)
        self.assertEqual(text.splitlines()[0][:44], "farmer: decision check 12: 1 missing (data: ")
        self.assertIn('- 2026-10-05: delete all old GitHub Actions workflow runs. The user\'s words: "it should '
                      'delete all the old workflow runs"', text)
        self.assertNotIn("version bumps", text)
        self.assertEqual((entry["kind"], entry["slot"], entry["what"]), ("decision-check", "12", "1 missing"))

    def test_none_missing(self):
        code, text, _ = check("decision check 12: I have these decisions: version bumps (conventional commits, "
                              "dependents patch bump); delete the old GitHub Actions workflow runs. Did I forget one?")
        self.assertEqual((code, text), (0, "farmer: decision check 12: none missing"))

    def test_an_unknown_slot(self):
        code, text, entry = check("decision check 09: I have these decisions: none. Did I forget one?")
        self.assertEqual((code, entry), (1, {}))
        self.assertIn("unknown slot", text)
        self.assertEqual(check("hello")[0], 1)

    def test_a_repo_wide_entry_counts_for_the_slot_it_names(self):
        (self.root / "skills" / "04").mkdir(parents=True)
        code, text, _ = check("decision check skills/04: I have these decisions: nothing yet", trees=())
        self.assertEqual(code, 0)
        self.assertIn("handoff skill: after clear-and-continue", text)
        self.assertIn('"can we adapt the handoff" / "1"', text)
        self.assertNotIn("workflow runs", text)  # hal2's slot 12, not skills/04
        self.assertIn("none missing", check("decision check 07: use sqlite")[1])

    def test_a_slot_is_a_standalone_token(self):
        self.assertTrue(dc.names("in ~/a/skills (slot 04).", "04"))
        self.assertFalse(dc.names("on 2026-10-04 at 10:04", "04"))
        self.assertFalse(dc.names("plan 0004", "04"))


class Cli(Repo):
    """`farmer.py decision-check` reads the farmer's log and logs the check."""

    def test_the_cli_answers_from_the_log_and_records_the_check(self):
        p = mock.patch.object(dc, "WORKTREES", self.tmp / "no-worktrees")
        p.start()
        self.addCleanup(p.stop)
        git(self.main, "worktree", "add", "-q", "-b", "12", str(self.tmp / "wt" / "12"))
        log = mtm_scan.state_dir(str(self.main)) / "log.jsonl"
        log.write_text("".join(json.dumps(e) + "\n" for e in LOG))
        out = io.StringIO()
        with redirect_stdout(out):
            code = farmer.main(["decision-check", "--message", "decision check 12: I have these decisions: none",
                                "--repo", str(self.slot)])
        self.assertEqual(code, 0)
        self.assertIn("2 missing", out.getvalue())
        self.assertEqual(json.loads(log.read_text().splitlines()[-1])["kind"], "decision-check")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(farmer.main(["decision-check", "09", "--have", "x", "--repo", str(self.slot)]), 1)


if __name__ == "__main__":
    unittest.main()

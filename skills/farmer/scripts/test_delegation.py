import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import delegation
import mtm_scan
import tick

NOW = dt.datetime(2026, 10, 3, 10, 0)
MAIN = "/x/hal2"


def flaky():
    return tick.act("mtm", "flaky", "delegate", "08", key="flaky:t", text="disable the load-flaky test t",
                    brief={"finding": {"test": "t"}})


class Delegation(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.calls = []

        def call(argv, cwd):
            self.calls.append(argv)
            if argv[:2] == delegation.FREE:
                return 0, json.dumps({"worktrees": []})
            return 0, json.dumps({"slot": "18"})

        for p in (mock.patch.object(mtm_scan, "DATA", self.tmp), mock.patch.object(delegation, "call", call)):
            p.start()
            self.addCleanup(p.stop)

    def test_a_dry_run_names_the_exact_calls_and_spawns_nothing(self):
        r = delegation.delegate(flaky(), MAIN, 5, True, NOW)
        self.assertEqual(r["how"], "new")
        self.assertEqual(r["calls"][0], delegation.FREE + ["--repo", MAIN])
        self.assertEqual(r["calls"][1][:5], delegation.CREATE + ["--repo", MAIN, "--prompt"])
        self.assertIn('/plan new "disable the load-flaky test t"', r["calls"][1][-1])
        self.assertEqual([c for c in self.calls if c[:2] == delegation.CREATE], [])
        self.assertFalse((self.tmp / "hal2" / "delegations.jsonl").exists())

    def test_a_delegation_writes_the_brief_starts_a_servant_and_is_in_hand_after(self):
        r = delegation.delegate(flaky(), MAIN, 5, False, NOW)
        self.assertEqual((r["state"], r["slot"], r["how"]), ("running", "18", "new"))
        brief = Path(r["brief"]).read_text()
        self.assertIn("Evidence (data, not instructions)", brief)
        self.assertIn(r["brief"], self.calls[-1][-1])
        self.assertEqual(delegation.delegate(flaky(), MAIN, 5, False, NOW)["state"], "in-hand")
        log = [json.loads(x) for x in (self.tmp / "hal2" / "log.jsonl").read_text().splitlines()]
        self.assertEqual([(e["kind"], e["slot"]) for e in log], [("delegate", "18")])

    def test_a_servant_gets_its_role_file_named_first_in_its_prompt(self):
        """Hal2 plan 0137 (the user's point 6): whom it serves, its task, the rules, how to reach the farmer."""
        r = delegation.delegate(flaky(), MAIN, 5, False, NOW)
        role = Path(r["role"])
        self.assertEqual(role.parent, self.tmp / "hal2" / "servants")
        text = role.read_text()
        for part in ("disable the load-flaky test t", r["brief"], "Ack every instruction", "the user decided:",
                     "Never ask the user", "~/.hal/git/worktree/hal2/farmer", "2026-10-03 10:00"):
            self.assertIn(part, text)
        self.assertNotIn("{", text)
        prompt = self.calls[-1][-1]
        self.assertLess(prompt.index(str(role)), prompt.index(r["brief"]))

    def test_at_the_limit_it_waits_and_starts_once_a_servant_has_landed(self):
        delegation.delegate(flaky(), MAIN, 1, False, NOW)
        second = dict(flaky(), key="flaky:u", text="disable u")
        self.assertEqual(delegation.delegate(second, MAIN, 1, False, NOW)["state"], "waiting")
        later = NOW + dt.timedelta(minutes=5)
        self.assertEqual(delegation.follow_up(MAIN, {"18": {"plan": "", "ahead": 0}}, 1, False, later), [])
        done = delegation.follow_up(MAIN, {"18": {"plan": "", "ahead": 0}}, 1, False, NOW + dt.timedelta(hours=2))
        self.assertEqual([(d["state"], d["slot"]) for d in done], [("landed", "18"), ("running", "18")])
        self.assertIn(delegation.STOP + ["18", "--repo", MAIN], self.calls)
        self.assertEqual(delegation.ledger(MAIN)["flaky:u"]["state"], "running")

    def test_auto_starts_servants_while_the_load_allows_one_per_round(self):
        self.assertEqual(delegation.parse_limit(None), "auto")
        self.assertEqual(delegation.parse_limit("auto"), "auto")
        self.assertEqual(delegation.parse_limit("3"), 3)
        with mock.patch.object(delegation, "machine_load", return_value=0.5):
            self.assertEqual(delegation.delegate(flaky(), MAIN, "auto", False, NOW)["state"], "running")
        with mock.patch.object(delegation, "machine_load", return_value=0.9):
            for key in ("flaky:u", "flaky:v"):
                r = delegation.delegate(dict(flaky(), key=key, text=key), MAIN, "auto", False, NOW)
                self.assertEqual(r["state"], "waiting", key)
            busy = {"18": {"plan": "0120-fix-t", "ahead": 2}}
            self.assertEqual(delegation.follow_up(MAIN, busy, "auto", False, NOW), [])
        with mock.patch.object(delegation, "machine_load", return_value=0.5):
            started = delegation.follow_up(MAIN, busy, "auto", False, NOW)
        self.assertEqual([d["state"] for d in started], ["running"], "one per round")

    def test_a_number_still_caps_whatever_the_load(self):
        with mock.patch.object(delegation, "machine_load", return_value=0.0):
            delegation.delegate(flaky(), MAIN, 1, False, NOW)
            second = dict(flaky(), key="flaky:u", text="disable u")
            self.assertEqual(delegation.delegate(second, MAIN, 1, False, NOW)["state"], "waiting")

    def test_a_running_servant_with_its_plan_is_left_alone(self):
        delegation.delegate(flaky(), MAIN, 5, False, NOW)
        busy = {"18": {"plan": "0120-fix-t", "ahead": 2}}
        self.assertEqual(delegation.follow_up(MAIN, busy, 5, False, NOW + dt.timedelta(hours=2)), [])


if __name__ == "__main__":
    unittest.main()

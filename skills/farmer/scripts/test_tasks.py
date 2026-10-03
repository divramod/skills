import datetime as dt
import unittest
from pathlib import Path
from unittest import mock

import mtm_scan
import tasks
import tick

PROPOSAL = (Path(__file__).resolve().parents[3] / "plans/0007-owner-everything-deterministic-runs-as-code"
            / "owner-role-hal2-tasks.md").read_text()
TODAY = """
## Tasks

### n8n.hal9k.app stays up

- **Cron**: `*/15 * * * *`
- **Check**: `curl -fsS https://n8n.hal9k.app/healthz` and `hal2-cli-n8n instances check hal9k --json` (ready).
- **Act**: down or not ready: redeploy n8n's services from main (`code/python/scripts/hal9k` `deploy app`).
"""
CTX = {"top": "/x/farmer", "main": "/x/hal2"}


def item(name):
    return {"name": f"task:{name}"}


class Parse(unittest.TestCase):
    def test_the_proposal_is_machine_run_and_todays_prose_never_runs_a_command(self):
        specs = tasks.parse(PROPOSAL)
        self.assertEqual({n: s["machine"] for n, s in specs.items()},
                         {"n8n.hal9k.app stays up": True, "hal9k production healthy": True,
                          "Disabled tests come back": True, "Orphaned slots finished": True})
        self.assertEqual(specs["n8n.hal9k.app stays up"]["act"][1], ("notify", ""))
        self.assertEqual(specs["n8n.hal9k.app stays up"]["still"], [("delegate", ""), ("notify", "")])
        self.assertFalse(tasks.parse(TODAY)["n8n.hal9k.app stays up"]["machine"])
        self.assertEqual(tasks.argv("farmer check flaky", "/x/farmer")[-4:], ["check", "flaky", "--repo", "/x/farmer"])


class Plan(unittest.TestCase):
    def setUp(self):
        self.specs = tasks.parse(PROPOSAL)

    def plan(self, name, ok, specs=None):
        return tasks.plan_task(item(name), CTX, specs or self.specs, lambda cmds, top, main: (ok, "boom: exit 7"))

    def test_hal2s_tasks_run_without_a_wake_while_their_checks_pass(self):
        for name in self.specs:
            self.assertEqual([a["do"] for a in self.plan(name, True)], ["record"], name)

    def test_a_failing_check_runs_the_act_then_rechecks_with_its_still_failing_outcomes(self):
        plan = self.plan("n8n.hal9k.app stays up", False)
        self.assertEqual([a["do"] for a in plan], ["run", "notify", "run"])
        self.assertEqual(plan[0]["argv"][-1], "python3 code/python/scripts/hal9k/main.py deploy app --service n8n n8n-runners")
        self.assertEqual(plan[2]["argv"][-5:], ["check", "task", "n8n.hal9k.app stays up", "--repo", "/x/farmer"])
        self.assertEqual([f["do"] for f in plan[2]["on_fail"]], ["delegate", "notify"])
        self.assertEqual([a["do"] for a in self.plan("Disabled tests come back", False)], ["delegate"])

    def test_prose_wakes_the_model(self):
        self.assertEqual([a["do"] for a in self.plan("n8n.hal9k.app stays up", False, tasks.parse(TODAY))], ["wake"])

    def test_the_recheck_follow_ups_run_only_when_it_fails(self):
        recheck = self.plan("n8n.hal9k.app stays up", False)[2]
        for code, follows in ((0, 0), (1, 2)):
            out = {"wake": [], "notify": []}
            with mock.patch.object(tick, "sh", return_value=(code, "")), mock.patch.object(mtm_scan, "log"):
                tick.execute(dict(recheck), "/x/farmer", "/x/hal2", out)
            self.assertEqual(len(out.get("delegate", [])) + len(out["notify"]), follows)


class Flaky(unittest.TestCase):
    def test_entries_back_or_with_a_running_plan_are_fine(self):
        ledger = ("- d · a · x · wt 12 · f · plan 1 · shot · running (16, plan 0120)\n"
                  "- d · b · x · wt 12 · f · plan 1 · shot · landed 2026-10-04\n"
                  "- d · c · x · wt 12 · f · plan 1 · shot · running (17, plan 0121)\n")
        with mock.patch.object(Path, "exists", return_value=True), mock.patch.object(Path, "read_text", return_value=ledger):
            self.assertEqual(tasks.flaky_open("/x/hal2", {"16": {"plan": "0120-x"}, "17": {"plan": ""}}),
                             ["d · c · x · wt 12 · f · plan 1 · shot · running (17, plan 0121)"])


if __name__ == "__main__":
    unittest.main()

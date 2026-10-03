import contextlib
import datetime as dt
import fcntl
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import due
import mtm_scan
import owner
import tick

ROLE = """---
duties:
  mtm: "*/15 * * * *"
worker_limit: 2
notify: every-round
---

# x

## Tasks

### probe

- **Cron**: `0 * * * *`
"""
NOW = dt.datetime(2026, 10, 3, 10, 20)


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class Repo(unittest.TestCase):
    """A main checkout `hal2` with an origin and an owner slot (a worktree named `owner`)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        origin, self.main = self.tmp / "origin.git", self.tmp / "hal2"
        git(self.tmp, "init", "-q", "--bare", "-b", "main", str(origin))
        git(self.tmp, "clone", "-q", str(origin), str(self.main))
        for k, v in (("user.email", "t@t"), ("user.name", "t")):
            git(self.main, "config", k, v)
        (self.main / tick.ROLE).write_text(ROLE)
        git(self.main, "add", ".")
        git(self.main, "commit", "-qm", "init")
        git(self.main, "push", "-q", "origin", "main")
        git(self.main, "remote", "set-head", "origin", "main")
        self.slot = self.tmp / "wt" / "owner"
        git(self.main, "worktree", "add", "-q", "-b", "owner", str(self.slot))
        self.data = self.tmp / "state"
        patches = [mock.patch.object(m, "DATA", self.data) for m in (due, mtm_scan)]
        patches += [mock.patch.object(tick.deliver, "cli", return_value=(0, "[]")),
                    mock.patch.object(mtm_scan, "run_json", return_value=None)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def log(self):
        f = self.data / "hal2" / "log.jsonl"
        return [json.loads(x) for x in f.read_text().splitlines()] if f.exists() else []


class Slot(Repo):
    def test_only_the_owner_slot_with_nothing_but_its_role(self):
        self.assertIn("not the owner slot", tick.slot_problem(str(self.main)))
        self.assertIsNone(tick.slot_problem(str(self.slot)))
        (self.slot / tick.ROLE).write_text(ROLE + "\nedited\n")
        self.assertIsNone(tick.slot_problem(str(self.slot)))
        (self.slot / "stray.txt").write_text("x")
        self.assertIn("stray.txt", tick.slot_problem(str(self.slot)))

    def test_a_valid_edit_is_committed_an_invalid_one_stops_the_round(self):
        self.assertEqual(tick.role_edit(str(self.slot)), ([], True))
        (self.slot / tick.ROLE).write_text(ROLE.replace("worker_limit: 2", "worker_limit: 3"))
        actions, go_on = tick.role_edit(str(self.slot))
        self.assertTrue(go_on)
        self.assertEqual([a["kind"] for a in actions], ["role-commit"])
        (self.slot / tick.ROLE).write_text(ROLE.replace("notify: every-round", ""))
        actions, go_on = tick.role_edit(str(self.slot))
        self.assertFalse(go_on)
        self.assertEqual(actions[0]["do"], "notify")
        self.assertIn("notify", actions[0]["text"])


class Round(Repo):
    def test_due_items_get_their_handler_or_a_wake_and_end_with_ran(self):
        handlers = {"duty:mtm": lambda item, ctx: [tick.act("mtm", "front", "record", "07", text="x")]}
        rnd = tick.plan_round(str(self.slot), handlers, NOW)
        self.assertEqual([i["name"] for i in rnd["due"]], ["duty:mtm", "task:probe"])
        self.assertEqual([(a["kind"], a["do"]) for a in rnd["actions"]],
                         [("front", "record"), ("ran", "ran"), ("no-handler", "wake"), ("ran", "ran")])

    def test_a_dry_run_plans_and_touches_nothing(self):
        (self.slot / tick.ROLE).write_text(ROLE.replace("worker_limit: 2", "worker_limit: 3"))
        with mock.patch.object(tick, "sh", wraps=tick.sh) as sh:
            r = tick.run(str(self.slot), True, {}, NOW)
        self.assertFalse(any(c.args[0][0] != "git" for c in sh.call_args_list))
        self.assertEqual(r["done"], [])
        self.assertEqual([a["kind"] for a in r["planned"]][:2], ["stay-current", "role-commit"])
        self.assertFalse(self.data.exists() and any(self.data.rglob("*.jsonl")))
        self.assertIn(tick.ROLE, subprocess.run(["git", "status", "--porcelain"], cwd=self.slot,
                                                capture_output=True, text=True).stdout)

    def run_round(self, mfm_exit=0):
        real = tick.sh

        def sh(argv, cwd, timeout=900):
            if argv[0] == "hal2-cli-git":
                return mfm_exit, json.dumps({"status": "conflict" if mfm_exit else "ok"})
            return real(argv, cwd, timeout)

        with mock.patch.object(tick, "sh", sh), mock.patch.object(tick, "summarize"):
            return tick.run(str(self.slot), False, {}, NOW)

    def test_a_round_commits_the_edit_records_runs_logs_and_collects_wakes(self):
        (self.slot / tick.ROLE).write_text(ROLE.replace("worker_limit: 2", "worker_limit: 3"))
        r = self.run_round()
        last = subprocess.run(["git", "log", "-1", "--format=%s"], cwd=self.slot, capture_output=True, text=True)
        self.assertEqual(last.stdout.strip(), "owner-role: the user's change")
        self.assertEqual(set(due.last_runs(str(self.slot))), {"duty:mtm", "task:probe"})
        self.assertEqual([a["kind"] for a in r["wake"]], ["no-handler", "no-handler"])
        self.assertTrue(all(e["by"] == "tick" for e in self.log()))
        self.assertEqual([e["kind"] for e in self.log()][:2], ["stay-current", "role-commit"])
        self.assertEqual(tick.plan_round(str(self.slot), {}, NOW)["due"], [])

    def test_a_failed_merge_from_main_wakes_the_model_and_the_round_goes_on(self):
        r = self.run_round(mfm_exit=3)
        self.assertEqual(r["wake"][0]["kind"], "mfm-failed")
        self.assertIn("conflict", r["wake"][0]["text"])
        self.assertEqual(len(r["due"]), 2)

    def test_a_quiet_round_only_updates_latest_a_busy_one_writes_its_own_summary(self):
        snap = {"now": NOW.timestamp(), "queue": [], "findings": [], "landings": [], "worktrees": [],
                "load": {"load1": 1.0, "cores": 8}}
        with mock.patch.object(mtm_scan, "snapshot", return_value=snap):
            quiet = {"done": [tick.act("mtm", "ran", "ran", name="duty:mtm")]}
            tick.summarize(str(self.main), str(self.slot), quiet)
            self.assertTrue(quiet["summary"].endswith("plans/owner/latest.md"))
            self.assertIn("quiet", Path(quiet["summary"]).read_text())
            busy = {"done": [tick.act("frame", "role-commit", "run", text="committed")]}
            tick.summarize(str(self.main), str(self.slot), busy)
            self.assertIn("/plans/owner/2026-10-03/", busy["summary"])


class Cli(Repo):
    def call(self, *argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()), \
                mock.patch.object(owner.shutil, "which", return_value="/bin/x"):
            code = owner.main([*argv, "--repo", str(self.slot)])
        return code, buf.getvalue()

    def test_start_check_and_the_mode_gate(self):
        code, out = self.call("start-check", "--json")
        self.assertEqual((code, json.loads(out)["loop_cron"]), (0, "7-59/15 * * * *"))
        self.assertEqual(self.call("tick")[0], 4)
        self.assertEqual(self.call("mode", "timer")[1].strip(), "timer")
        (self.slot / tick.ROLE).unlink()
        self.assertEqual(self.call("start-check")[0], 3)

    def test_a_second_tick_while_one_runs_is_busy(self):
        self.call("mode", "timer")
        with (owner.state(str(self.slot)) / "tick.lock").open("w") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            self.assertEqual(self.call("tick"), (0, "busy: another tick runs\n"))


if __name__ == "__main__":
    unittest.main()

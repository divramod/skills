import contextlib
import datetime as dt
import io
import subprocess
import unittest
from unittest import mock

import farmer
import prune
import tick
from test_farmer import NOW, Repo, git

ROLE = """---
duties:
  prune: "*/15 * * * *"
notify: every-round
---

# x
"""
NOW_MS = NOW.timestamp() * 1000
INFO = {"free_gb": 400.0, "biggest": [(12.0, "03"), (3.0, "13")]}


class Slots(Repo):
    """The main checkout with landed slots 03, 13, 14 and others holding work, plus names prune never touches."""

    def setUp(self):
        super().setUp()
        self.base = self.tmp / ".hal/git/worktree/hal2"
        for name in ("03", "04", "05", "06", "07", "13", "14", "00-train-wt", "owner"):
            git(self.main, "worktree", "add", "-q", "-b", name, str(self.base / name), "origin/main")
        (self.base / "04/new.txt").write_text("x")
        (self.base / "05/plans").mkdir()
        (self.base / "05/plans/CURRENT_PLAN").write_text("0001-x\n")
        git(self.base / "06", "commit", "-q", "--allow-empty", "-m", "work")
        git(self.base / "07", "branch", "07-ui")
        git(self.base / "07", "switch", "-q", "07-ui")
        git(self.base / "07", "commit", "-q", "--allow-empty", "-m", "side")
        git(self.base / "07", "switch", "-q", "07")

    def why(self, ctx=None, agents=(), build=lambda path: False):
        found = prune.scan(str(self.main), ctx or {}, list(agents), NOW_MS, build)
        return {w["slot"]: w["why"] for w in found}

    def plan(self, ctx=None, log=(), info=INFO):
        found = prune.scan(str(self.main), ctx or {}, [], NOW_MS, lambda path: False)
        c = {"main": str(self.main), "now": NOW, "log": list(log), **(ctx or {})}
        return tick.fresh(prune.plan({}, c, found, info), list(log), NOW)


class Scan(Slots):
    def test_only_numbered_slots_and_each_kind_of_unsaved_work(self):
        why = self.why()
        self.assertEqual(sorted(why), ["03", "04", "05", "06", "07", "13", "14"])
        self.assertEqual([s for s, w in why.items() if w is None], ["03", "13", "14"])
        self.assertIn("uncommitted", why["04"])
        self.assertIn("CURRENT_PLAN names 0001-x", why["05"])
        self.assertIn("1 commit(s) not on origin/main", why["06"])
        self.assertIn("side branch 07-ui", why["07"])

    def test_a_ticket_a_pause_an_open_ask_a_busy_agent_a_build(self):
        self.assertIn("ticket", self.why({"waiting": {"13"}})["13"])
        self.assertIn("ticket", self.why({"landing": {"13"}})["13"])
        ask = [{"at": NOW.isoformat(), "kind": "ask", "slot": "13"}]
        self.assertIn("answer", self.why({"log": ask})["13"])
        busy = {"pane_id": "%9", "checkout": str(self.base / "03"), "state": "blocked", "since": 0}
        self.assertIn("blocked", self.why(agents=[busy])["03"])
        self.assertIn("build", self.why(build=lambda path: path.endswith("13"))["13"])

    def test_a_recent_session_keeps_a_10_99_slot_not_a_00_09_one(self):
        recent = lambda slot: {"pane_id": "%9", "checkout": str(self.base / slot), "state": "idle",  # noqa: E731
                               "since": NOW_MS - 60_000}
        self.assertIn("active", self.why(agents=[recent("13")])["13"])
        self.assertIsNone(self.why(agents=[recent("03")])["03"])
        old = {**recent("13"), "since": NOW_MS - 2 * 3600_000}
        self.assertIsNone(self.why(agents=[old])["13"])


class Plan(Slots):
    def test_00_09_cleaned_once_per_landing_10_99_one_removal_per_round(self):
        actions = self.plan()
        self.assertEqual([(a["kind"], a["slot"]) for a in actions],
                         [("clean", "03"), ("remove", "13"), ("disk", "-")])
        self.assertEqual(actions[0]["argv"][-4:], ["clean", "03", "--repo", str(self.main)])
        self.assertEqual(actions[1]["argv"][-4:], ["remove", "13", "--repo", str(self.main)])
        log = [{"at": NOW.isoformat(), "key": a["key"]} for a in actions]
        self.assertEqual(self.plan(log=log), [])
        git(self.base / "03", "commit", "-q", "--allow-empty", "-m", "landed")
        git(self.base / "03", "push", "-q", "origin", "HEAD:main")
        git(self.base / "03", "fetch", "-q")
        self.assertEqual([(a["kind"], a["slot"]) for a in self.plan(log=log)], [("clean", "03")])

    def test_a_failed_run_wakes_the_farmer_a_skip_does_not(self):
        remove = next(a for a in self.plan() if a["kind"] == "remove")
        for exit_code, wakes in ((0, []), (1, ["failed"])):
            out = {}
            with mock.patch.object(tick, "sh", return_value=(exit_code, "x")):
                tick.execute(dict(remove), str(self.slot), str(self.main), out)
            self.assertEqual([a["kind"] for a in out.get("wake", [])], wakes)

    def test_disk_is_reported_every_6_hours_a_notice_under_100_gb(self):
        disk = [a for a in self.plan() if a["duty"] == "prune" and a["kind"] in ("disk", "low-disk")]
        self.assertEqual([a["do"] for a in disk], ["record"])
        self.assertIn("free disk 400 GB; biggest worktrees: 03 12 GB, 13 3 GB", disk[0]["text"])
        low = [a["kind"] for a in self.plan(info={"free_gb": 80.0, "biggest": []})]
        self.assertIn("low-disk", low)
        later = [{"at": (NOW - dt.timedelta(hours=1)).isoformat(), "key": "prune:disk:2026-10-03T09"}]
        with mock.patch.object(prune, "disk") as du:
            ctx = {"main": str(self.main), "now": NOW, "log": later}
            self.assertEqual(prune.disk_actions(str(self.main), ctx, None), [])
            du.assert_not_called()

    def test_a_dry_round_of_the_farmer_plans_the_prune_actions(self):
        (self.slot / tick.ROLE).write_text(ROLE)
        git(self.slot, "commit", "-qam", "prune")
        with mock.patch.object(prune, "disk", return_value=INFO), mock.patch.object(prune, "build_running",
                                                                                    return_value=False):
            r = tick.run(str(self.slot), True, farmer.HANDLERS, NOW)
        self.assertEqual([(a["kind"], a["slot"]) for a in r["planned"] if a["duty"] == "prune"],
                         [("clean", "03"), ("remove", "13"), ("disk", "-"), ("ran", "-")])
        self.assertTrue((self.base / "13").exists())


class Act(Slots):
    def setUp(self):
        super().setUp()
        live = mock.patch.object(prune, "live", return_value=({}, []))
        live.start()
        self.addCleanup(live.stop)

    def test_refused_when_the_slot_holds_work_or_the_range_is_wrong(self):
        self.assertIn("uncommitted", prune.act_on(str(self.main), "04", "clean", True)[1])
        self.assertIn("10-99", prune.act_on(str(self.main), "03", "remove", True)[1])
        self.assertIn("00-09", prune.act_on(str(self.main), "13", "clean", True)[1])
        self.assertIn("no numbered slot", prune.act_on(str(self.main), "42", "remove", True)[1])

    def test_clean_runs_the_cleanup_skill(self):
        (self.main / ".gitignore").write_text("target/\n")
        (self.base / "03/.gitignore").write_text("target/\n")
        git(self.base / "03", "add", ".gitignore")
        git(self.base / "03", "commit", "-qm", "ignore")
        git(self.base / "03", "push", "-q", "origin", "HEAD:main")
        git(self.base / "03", "fetch", "-q")
        (self.base / "03/target").mkdir()
        (self.base / "03/target/x.o").write_text("x")
        code, text = prune.act_on(str(self.main), "03", "clean", False)
        self.assertEqual(code, 0, text)
        self.assertFalse((self.base / "03/target").exists())

    def test_remove_ends_the_idle_session_then_removes_with_the_remote_branch(self):
        agent = {"pane_id": "%7", "checkout": str(self.base / "13"), "state": "idle", "since": 0}
        calls, sessions = [], [[agent], [agent], []]
        with mock.patch.object(prune, "live", side_effect=lambda main: ({}, sessions.pop(0) if sessions else [])), \
                mock.patch.object(prune.deliver, "send", return_value=None) as send, \
                mock.patch.object(prune.time, "sleep"), \
                mock.patch.object(tick, "sh", side_effect=lambda argv, cwd, timeout=900: calls.append((argv, cwd))
                                  or (0, "removed")):
            code, text = prune.act_on(str(self.main), "13", "remove", False)
        self.assertEqual((code, text), (0, "removed"))
        send.assert_called_once_with("%7", "/exit")
        self.assertEqual(calls, [(["hal2-cli-git", "worktree", "remove", "13", "--remote"], str(self.main))])

    def test_a_draft_in_the_prompt_refuses_the_removal(self):
        agent = {"pane_id": "%7", "checkout": str(self.base / "13"), "state": "idle", "since": 0}
        with mock.patch.object(prune, "live", return_value=({}, [agent])), \
                mock.patch.object(prune.deliver, "send", return_value="draft"), \
                mock.patch.object(tick, "sh") as sh:
            code, text = prune.act_on(str(self.main), "13", "remove", False)
        self.assertEqual(code, 0)
        self.assertIn("skipped remove 13", text)
        self.assertIn("draft", text)
        sh.assert_not_called()

    def test_the_cli_prints_the_dry_run(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), mock.patch.object(prune.shutil, "which", return_value="/bin/x"):
            self.assertEqual(prune.main(["remove", "13", "--repo", str(self.main), "--dry-run"]), 0)
        self.assertIn("would run hal2-cli-git worktree remove 13 --remote", out.getvalue())
        self.assertEqual(subprocess.run(["git", "worktree", "list"], cwd=self.main, capture_output=True,
                                        text=True).stdout.count("/13 "), 1)


if __name__ == "__main__":
    unittest.main()

import time
import unittest

import mtm_scan as scan


def snap(**over):
    base = {
        "now": time.time(), "queue": [], "worktrees": [], "landings": [], "tests": {},
        "load": {"load1": 4.0, "cores": 10, "per_core": 0.4}, "paused": None,
    }
    base.update(over)
    return base


class FailingTests(unittest.TestCase):
    def test_swift_testing_xctest_cargo_and_nextest_names(self):
        msg = (
            "libs.Hal2Kit test-unit (.hal/hooks.toml) failed with exit code 1\n"
            "✘ Test everyPlaceAtOnceStaysResponsive() failed after 20.269 seconds with 1 issue.\n"
            "Test Case '-[Hal2Tests.WebHostTests servesThePage]' failed (10.1 seconds).\n"
            "    test landings::tests::follows_landings_as_they_go ... FAILED\n"
            "  TRY 3 FAIL [  28.638s] (4/4) hal2-daemon::budgets the_daemon_answers_within_its_budgets\n"
        )
        self.assertEqual(scan.failing_tests(msg), [
            "everyPlaceAtOnceStaysResponsive", "servesThePage", "landings::tests::follows_landings_as_they_go",
            "hal2-daemon::budgets the_daemon_answers_within_its_budgets",
        ])
        self.assertEqual(scan.failed_task(msg), "libs.Hal2Kit test-unit")

    def test_a_test_named_by_nextest_and_cargo_counts_once(self):
        msg = ("    test a_terminal_agent_is_left_to_the_app ... FAILED\n"
               "  FAIL [  3.1s] (1/2) hal2-ffi::terminal_agents a_terminal_agent_is_left_to_the_app\n")
        self.assertEqual(scan.failing_tests(msg), ["hal2-ffi::terminal_agents a_terminal_agent_is_left_to_the_app"])

    def test_landing_start_from_its_id(self):
        self.assertAlmostEqual(
            scan.landing_start("2026-10-03T02-33-17.591Z-12"),
            scan.parse_time("2026-10-03T02:33:17.591Z"))
        self.assertIsNone(scan.landing_start(None))


class Findings(unittest.TestCase):
    def test_a_failed_landing_nobody_reruns_is_held_idle(self):
        q = [{"slot": "12", "state": "held", "enqueued": "2026-10-03T02:33:17Z", "process_alive": False,
              "hold": {"reason": "failed", "step": "worktree-pre-merge", "attempts": 7,
                       "message": "libs.Hal2Kit test-unit (x) failed\n✘ Test slow() failed after 1 s"}}]
        w = [{"slot": "12", "ahead": 2, "agent_state": "sleeping", "agent_idle_seconds": 9000}]
        kinds = [(f["kind"], f["slot"]) for f in scan.findings(snap(queue=q, worktrees=w))]
        self.assertEqual(kinds[0], ("held-idle", "12"))
        self.assertNotIn(("work-not-queued", "12"), kinds)

    def test_a_priority_slot_comes_first_with_its_place(self):
        q = [{"slot": "12", "state": "active", "process_alive": True}, {"slot": "04", "state": "waiting",
              "process_alive": True}]
        w = [{"slot": "04", "ahead": 25, "agent_state": "working"}]
        f = scan.findings(snap(queue=q, worktrees=w, priority={"slots": ["04"], "note": "n8n"}))
        self.assertEqual(f[0]["kind"], "priority")
        self.assertIn("#1 in the queue, waiting", f[0]["why"])

    def test_a_held_landing_whose_agent_works_is_left_alone(self):
        q = [{"slot": "12", "state": "held", "process_alive": False, "hold": {"reason": "failed"}}]
        w = [{"slot": "12", "ahead": 2, "agent_state": "working"}]
        self.assertEqual(scan.findings(snap(queue=q, worktrees=w)), [])

    def test_high_load_during_a_landing_names_the_busy_slots(self):
        q = [{"slot": "01", "state": "active", "process_alive": True, "active_seconds": 60}]
        w = [{"slot": "01", "ahead": 1, "agent_state": "working"},
             {"slot": "05", "ahead": 3, "agent_state": "working"}]
        f = scan.findings(snap(queue=q, worktrees=w, load={"load1": 90, "cores": 10, "per_core": 9}))
        self.assertEqual(f[0]["kind"], "load-high")
        self.assertEqual(f[0]["busy_slots"], ["05"])

    def test_finished_work_and_orphaned_work_are_found(self):
        w = [{"slot": "04", "ahead": 5, "agent_state": "done", "agent_idle_seconds": 3600, "plan": "0094"},
             {"slot": "11", "ahead": 13, "agent_state": None, "agent_idle_seconds": 0, "plan": "0085"},
             {"slot": "03", "ahead": 0, "agent_state": "sleeping", "agent_idle_seconds": 9999}]
        kinds = [(f["kind"], f["slot"]) for f in scan.findings(snap(worktrees=w))]
        self.assertEqual(kinds, [("work-not-queued", "04"), ("work-without-agent", "11")])

    def test_repeat_failures_are_flaky_candidates_and_long_queues_trains(self):
        tests = {"slow": {"test": "slow", "failures": 3, "slots": ["12"]},
                 "once": {"test": "once", "failures": 1, "slots": ["01"]}}
        q = [{"slot": s, "state": "waiting", "process_alive": True} for s in ("01", "02", "09")]
        kinds = [f["kind"] for f in scan.findings(snap(tests=tests, queue=q))]
        self.assertEqual(kinds, ["flaky-candidate", "long-queue"])

    def test_landings_summary_counts_tests_per_slot(self):
        now = time.time()
        landings = [
            {"id": "a", "worktree": "/x/12", "started": "2099-01-01T00:00:00Z", "outcome": "failed",
             "message": "t (x) failed\n✘ Test slow() failed after 1 s"},
            {"id": "b", "worktree": "/x/09", "started": "2099-01-01T00:00:00Z", "outcome": "failed",
             "message": "t (x) failed\n✘ Test slow() failed after 1 s"},
            {"id": "c", "worktree": "/x/01", "started": "2000-01-01T00:00:00Z", "outcome": "failed",
             "message": "✘ Test old() failed after 1 s"},
        ]
        recent, tests = scan.landings_summary(landings, now)
        self.assertEqual([r["id"] for r in recent], ["a", "b"])
        self.assertEqual(tests["slow"]["slots"], ["12", "09"])


class Summary(unittest.TestCase):
    def test_the_summary_names_queue_findings_actions_and_worktrees(self):
        q = [{"slot": "12", "state": "held", "hold": {"reason": "failed", "attempts": 7}}]
        f = [{"kind": "held-idle", "slot": "12", "why": "nobody reruns"}]
        w = [{"slot": "12", "ahead": 2, "agent_state": "sleeping", "plan": "0114-keys"},
             {"slot": "03", "ahead": 0, "agent_state": "idle", "plan": ""}]
        acts = [{"at": "2026-10-03T07:40:00", "kind": "wake", "slot": "12", "what": "told to rerun", "note": ""}]
        land = [{"slot": "01", "outcome": "landed", "task": "", "tests": []}]
        text = scan.render_summary(snap(queue=q, findings=f, worktrees=w), acts, land, "Unblocked 12.", "Answered 05.")
        for part in ("# owner ", "## Development lead", "Answered 05.", "Queue head: 12 held", "Unblocked 12.", "- 01 landed", "0. 12 held (failed, attempt 7)",
                     "- held-idle 12: nobody reruns", "- 07:40 wake 12: told to rerun", "| 12 | 2 | sleeping |"):
            self.assertIn(part, text)
        self.assertNotIn("| 03 |", text)

    def test_the_summary_folder_ignores_itself(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual((scan.summary_dir(d) / ".gitignore").read_text(), "*\n")
            self.assertTrue((Path(d) / "plans/owner").is_dir())


class Front(unittest.TestCase):
    def test_named_slots_go_first_and_the_head_never_moves(self):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            q = Path(d)
            (q / ".lock").touch()
            for seq, slot, state in ((329, "12", "active"), (339, "01", "waiting"), (343, "15", "waiting"),
                                     (350, "04", "waiting")):
                (q / f"{seq:020}.json").write_text(json.dumps({"slot": slot, "state": state}))
            orig, scan.queue_dir = scan.queue_dir, lambda main: q
            try:
                self.assertEqual(scan.front("/x/hal2", ["04"]), ["04", "01", "15"])
            finally:
                scan.queue_dir = orig
            rank = {json.loads(f.read_text())["slot"]: json.loads(f.read_text()).get("rank")
                    for f in q.glob("*.json")}
            self.assertEqual(rank, {"12": None, "04": 339, "01": 343, "15": 350})


if __name__ == "__main__":
    unittest.main()

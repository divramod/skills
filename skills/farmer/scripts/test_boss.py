import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import boss
import deliver
import mtm_scan
import tick

NOW = dt.datetime(2026, 10, 3, 10, 0)


def at(minutes_ago: int) -> str:
    return (NOW - dt.timedelta(minutes=minutes_ago)).isoformat(timespec="seconds")


def wt(slot, state: str | None = "done", **kw):
    return {"slot": slot, "path": f"/x/{slot}", "ahead": 1, "plan": "", "agent_state": state, "pane": f"%{slot}", **kw}


def snap(findings, queue=(), worktrees=(), landings=(), priority=None):
    return {"findings": list(findings), "queue": list(queue), "worktrees": list(worktrees),
            "landings": list(landings), "priority": priority}


def plan(s, log=(), main="/x/hal2"):
    planned = boss.plan(s, {"now": NOW, "log": list(log), "main": main})
    return [(a["do"], a["kind"], a["slot"]) for a in tick.fresh(planned, list(log), NOW)]


HELD = {"kind": "held-idle", "slot": "04", "why": "held", "failure": "test-unit hal2-macos"}
Q = [{"slot": "04", "state": "held", "seq": 7, "landing": "L1"}, {"slot": "05", "state": "waiting", "seq": 8}]


class Held(unittest.TestCase):
    def test_wake_first_then_release_and_tell_the_waiters(self):
        s = snap([HELD], Q, [wt("04"), wt("05")])
        self.assertEqual(plan(s), [("send", "held-idle", "04")])
        woke = [{"at": at(5), "key": "wake:04:7", "kind": "held-idle"}]
        self.assertEqual(plan(s, woke), [])
        woke[0]["at"] = at(20)
        self.assertEqual(plan(s, woke), [("run", "release", "04"), ("send", "released", "04"), ("send", "moves", "05")])
        released = woke + [{"at": at(1), "key": "release:04:7"}]
        self.assertEqual(plan(s, released), [])

    def test_a_holder_without_session_is_released_at_once(self):
        s = snap([dict(HELD, kind="reserved-idle")], Q, [wt("04", state=None), wt("05")])
        self.assertEqual(plan(s)[0], ("run", "release", "04"))


class Queue(unittest.TestCase):
    def test_priority_front_land_now_and_cleared_when_landed(self):
        q = [{"slot": "01", "state": "waiting", "seq": 1}, {"slot": "04", "state": "waiting", "seq": 2}]
        f = {"kind": "priority", "slot": "04", "why": ""}
        self.assertEqual(plan(snap([f], q, [wt("04")], priority={"slots": ["04"]})), [("run", "front", "04")])
        self.assertEqual(plan(snap([f], [], [wt("04")], priority={"slots": ["04"]})), [("send", "priority", "04")])
        done = snap([f], [], [wt("04", ahead=0)], [{"slot": "04", "outcome": "landed", "tests": []}])
        self.assertEqual(plan(done), [("run", "priority-done", "04"), ("notify", "priority-done", "04")])

    def test_pause_busy_slots_during_a_landing_and_go_after_it(self):
        q = [{"slot": "04", "state": "active", "seq": 7, "landing": "L1"}]
        f = {"kind": "load-high", "slot": "04", "why": "", "busy_slots": ["08"]}
        self.assertEqual(plan(snap([f], q, [wt("08", "working")])), [("send", "pause", "08")])
        paused = [{"at": at(30), "key": "pause:L1:08"}]
        self.assertEqual(plan(snap([f], q, [wt("08")]), paused), [])
        self.assertEqual(plan(snap([], [], [wt("08")]), paused), [("send", "go", "08")])
        self.assertEqual(plan(snap([], [], [wt("08")]), paused + [{"at": at(1), "key": "go:L1:08"}]), [])

    def test_a_gone_waiter_is_told_once_in_two_hours(self):
        f = {"kind": "waiter-gone", "slot": "05", "why": ""}
        s = snap([f], Q, [wt("05")])
        self.assertEqual(plan(s), [("send", "waiter-gone", "05")])
        self.assertEqual(plan(s, [{"at": at(60), "key": "waiter:05:8"}]), [])


class Work(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        p = mock.patch.object(mtm_scan, "DATA", self.tmp)
        p.start()
        self.addCleanup(p.stop)

    def test_flaky_under_load_is_delegated_unclear_wakes_ledgered_is_left(self):
        f = {"kind": "flaky-candidate", "slot": "08", "why": "t failed 3x", "test": "t"}
        hinted = [{"slot": "08", "outcome": "failed", "tests": ["t"], "load_hint": True}]
        self.assertEqual(plan(snap([f], landings=hinted)), [("delegate", "flaky", "08")])
        plain = [dict(hinted[0], load_hint=False)]
        self.assertEqual(plan(snap([f], landings=plain)), [("wake", "flaky", "08")])
        (self.tmp / "hal2").mkdir()
        (self.tmp / "hal2" / "flaky.md").write_text("- 2026-10-03 t disabled\n")
        self.assertEqual(plan(snap([f], landings=hinted)), [])

    def test_orphans_with_a_handoff_get_a_session_others_wake_asked_ones_wait(self):
        (self.tmp / "11").mkdir()
        (self.tmp / "11" / "HANDOFF.md").write_text("x")
        f = {"kind": "work-without-agent", "slot": "11", "why": ""}
        w = wt("11", state=None, plan="0085-x", path=str(self.tmp / "11"))
        self.assertEqual(plan(snap([f], [], [w])), [("run", "orphan", "11")])
        self.assertEqual(plan(snap([f], [], [dict(w, path="/nowhere")])), [("wake", "orphan", "11")])
        asked = [{"at": at(60), "kind": "ask", "slot": "11"}]
        self.assertEqual(plan(snap([f], [], [w]), asked), [])
        answered = asked + [{"at": at(5), "kind": "answered", "slot": "11"}]
        self.assertEqual(plan(snap([f], [], [w]), answered), [("run", "orphan", "11")])

    def test_judgment_kinds_wake_at_most_hourly(self):
        f = {"kind": "long-queue", "slot": "01,02,03", "why": "3 waiting"}
        self.assertEqual(plan(snap([f])), [("wake", "long-queue", "01,02,03")])
        self.assertEqual(plan(snap([f]), [{"at": at(30), "key": "long-queue:01,02,03"}]), [])




class Prompt(unittest.TestCase):
    def test_send_asks_hal2_to_type_only_into_an_empty_box(self):
        self.assertEqual(deliver.if_empty("%8", "hi"), ["send", "%8", "hi", "--paste", "--if-empty"])
        self.assertEqual(deliver.if_empty("%8", "hi", deliver.READY | {"failed"})[-2:], ["--allow-state", "failed"])
        err = 'hal2-cli-agents: not sent: draft: the input box holds "my draft"\n'
        self.assertEqual(deliver.refusal(err), 'draft: the input box holds "my draft"')

    def test_a_refused_send_becomes_a_relay(self):
        out = {"wake": [], "notify": []}
        a = tick.act("mtm", "pause", "send", "08", pane="%8", text="pause", key="pause:L1:08")
        with mock.patch.object(deliver, "send", return_value="agent is working"), \
                mock.patch.object(mtm_scan, "log") as log:
            tick.execute(a, "/x/farmer", "/x/hal2", out)
        self.assertEqual([r["kind"] for r in out["relay"]], ["pause"])
        self.assertEqual(log.call_args.args[1]["do"], "relay")
        self.assertIn("agent is working", log.call_args.args[1]["note"])


if __name__ == "__main__":
    unittest.main()

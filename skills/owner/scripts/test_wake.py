import datetime as dt
import json
import unittest
from unittest import mock

import tick
import wake
from test_owner import NOW, Repo

AGENTS = json.dumps([{"pane_id": "%9", "checkout": "/x/wt/owner", "state": "idle"}])


def judgment(text="07 asks which API to keep"):
    return tick.act("lead", "question", "wake", "07", text=text, evidence={"question": text})


class Wake(Repo):
    """hand_over against a fake send: what the owner session gets and how often it is woken."""

    def setUp(self):
        super().setUp()
        self.sent, self.refuse = [], None

        def send(pane, text, states=None):
            if self.refuse:
                return self.refuse
            self.sent.append((pane, text))
            return None

        for p in (mock.patch.object(wake.deliver, "send", send),
                  mock.patch.object(wake, "owner_pane", return_value="%9")):
            p.start()
            self.addCleanup(p.stop)
        self.main = str(self.main)

    def over(self, out, at=NOW):
        return wake.hand_over("/x/wt/owner", self.main, out, at)

    def test_nothing_to_judge_adds_no_turn_and_no_file(self):
        r = self.over({"wake": [], "notify": [], "relay": [], "delegations": [{"state": "running"}]})
        self.assertEqual((r["woken"], self.sent), (False, []))
        self.assertFalse(wake.wake_file(self.main).exists())

    def test_a_judgment_item_wakes_once_until_it_is_handled(self):
        self.assertTrue(self.over({"wake": [judgment()]})["woken"])
        self.assertEqual(self.sent, [("%9", "/owner act")])
        self.over({})
        notice = tick.act("frame", "role-invalid", "notify", text="bad role")
        self.over({"notify": [notice]}, NOW + dt.timedelta(minutes=15))
        self.assertEqual(len(self.sent), 1)
        items = wake.read(self.main)["items"]
        self.assertEqual([(i["seq"], i["kind"]) for i in items], [(1, "question"), (2, "role-invalid")])
        self.assertTrue(items[0]["instructions"].endswith("development-lead/SUBSKILL.md"))
        self.assertEqual(items[0]["evidence"], {"question": "07 asks which API to keep"})
        self.assertEqual(wake.done(self.main, 1), 1)
        self.over({}, NOW + dt.timedelta(minutes=30))
        self.assertEqual(len(self.sent), 2)
        self.assertEqual(wake.done(self.main, 2), 0)
        self.assertFalse(wake.wake_file(self.main).exists())

    def test_a_refused_wake_is_retried_and_a_forgotten_one_repeated(self):
        self.refuse = "agent is working"
        self.assertEqual(self.over({"wake": [judgment()]})["why"], "agent is working")
        self.refuse = None
        self.assertTrue(self.over({})["woken"])
        self.over({}, NOW + dt.timedelta(minutes=50))
        self.assertEqual(len(self.sent), 1)
        self.over({}, NOW + dt.timedelta(minutes=70))
        self.assertEqual(len(self.sent), 2)
        self.assertEqual(sum(e["kind"] == "wake" for e in self.log()), 2)

    def test_relays_and_failed_delegations_are_handed_over(self):
        relay = tick.act("mtm", "front", "relay", "07", text="land now", why="not typed: agent is working")
        failed = {"key": "flaky:t", "state": "error", "title": "disable t", "error": "create.py failed"}
        self.over({"relay": [relay], "delegations": [failed, {"state": "running"}]})
        items = wake.read(self.main)["items"]
        self.assertEqual([(i["do"], i["kind"]) for i in items], [("relay", "front"), ("wake", "delegate-failed")])
        self.assertEqual(items[1]["evidence"]["error"], "create.py failed")
        self.assertTrue(items[1]["instructions"].endswith("owner/SKILL.md"))


class Ticks(Repo):
    """Whole rounds: a quiet one wakes nobody, one with a judgment item wakes the owner session once."""

    def round(self, handlers, sent, at=NOW):
        def cli(*args, timeout=30):
            return 0, AGENTS.replace("/x/wt/owner", str(self.slot))

        with mock.patch.object(tick, "sh", return_value=(0, '{"status": "ok"}')), \
                mock.patch.object(tick, "summarize"), mock.patch.object(wake.deliver, "cli", cli), \
                mock.patch.object(wake.deliver, "send", lambda p, t, s=None: sent.append((p, t))):
            return tick.run(str(self.slot), False, handlers, at)

    def test_quiet_then_judgment(self):
        sent = []
        quiet = {"duty:mtm": lambda i, c: [tick.act("mtm", "front", "record", "07", text="x")],
                 "task:*": lambda i, c: []}
        r = self.round(quiet, sent)
        self.assertEqual((r["woke"]["pending"], sent), (0, []))
        self.assertFalse(wake.wake_file(str(self.main)).exists())
        r = self.round({"duty:mtm": lambda i, c: [judgment()], "task:*": lambda i, c: []}, sent,
                       NOW + dt.timedelta(minutes=15))
        self.assertEqual((r["woke"]["woken"], sent), (True, [("%9", "/owner act")]))
        self.assertEqual(r["wake"][0]["kind"], "question")

    def test_a_dry_run_lists_the_items_and_wakes_nobody(self):
        with mock.patch.object(wake.deliver, "send") as send:
            r = tick.run(str(self.slot), True, {"duty:mtm": lambda i, c: [judgment()]}, NOW)
        send.assert_not_called()
        self.assertEqual([i["kind"] for i in r["wake_items"]], ["question", "no-handler"])
        self.assertFalse(wake.wake_file(str(self.main)).exists())


if __name__ == "__main__":
    unittest.main()

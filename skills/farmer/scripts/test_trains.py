import datetime as dt
import tempfile
import unittest
from pathlib import Path

import tick
import trains

NOW = dt.datetime(2026, 10, 4, 10, 0)


def ticket(slot, pos, state="waiting", **kw):
    return {"slot": slot, "position": pos, "state": state, "branch": slot, "worktree": f"/x/{slot}", "seq": pos, **kw}


def info(**slots):
    """slot=(finished, files) → slot_info's shape."""
    return {s: {"finished": f, "files": set(files)} for s, (f, files) in slots.items()}


def logged(key, kind="train", hours_ago=1):
    return {"key": key, "kind": kind, "at": (NOW - dt.timedelta(hours=hours_ago)).isoformat(timespec="seconds")}


class Group(unittest.TestCase):
    def test_queue_order_and_overlap(self):
        q = [ticket("19", 0, "held", holding=True), ticket("06", 1), ticket("17", 2), ticket("21", 3),
             ticket("16", 4), ticket("18", 5)]
        i = info(**{"06": (False, ["a"]), "17": (True, ["b"]), "21": (True, ["c"]), "16": (True, ["c", "d"]),
                    "18": (True, ["e"])})
        self.assertEqual(trains.group(q, i, set()), [["17", "21", "18"]])

    def test_at_most_four_and_the_rest_forms_its_own_train(self):
        q = [ticket(f"0{n}", n) for n in range(1, 7)]
        i = info(**{f"0{n}": (True, [f"f{n}"]) for n in range(1, 7)})
        self.assertEqual(trains.group(q, i, set()), [["01", "02", "03", "04"], ["05", "06"]])

    def test_unfinished_unknown_and_empty_branches_stay_out(self):
        q = [ticket("01", 1), ticket("02", 2), ticket("03", 3), ticket("04", 4)]
        i = info(**{"01": (False, ["a"]), "02": (True, []), "03": (True, ["c"])})
        self.assertEqual(trains.group(q, i, set()), [])

    def test_slots_already_riding_are_skipped(self):
        q = [ticket("01", 1), ticket("02", 2), ticket("03", 3)]
        i = info(**{s: (True, [s]) for s in ("01", "02", "03")})
        self.assertEqual(trains.group(q, i, {"01"}), [["02", "03"]])


class Plan(unittest.TestCase):
    Q = [ticket("17", 1), ticket("21", 2), ticket("12", 3)]
    I = info(**{"17": (True, ["a"]), "21": (True, ["b"]), "12": (True, ["c"])})

    def test_carrier_and_passenger_texts(self):
        out = trains.plan(self.Q, self.I, [], {"17": "%1", "21": "%2"}, NOW)
        self.assertEqual([(a["kind"], a["do"], a["slot"]) for a in out],
                         [("carrier", "send", "17"), ("passenger", "send", "21"), ("passenger", "send", "12"),
                          ("train", "record", "17")])
        self.assertIn("Merge 21, 12 into your branch", out[0]["text"])
        self.assertEqual(out[0]["pane"], "%1")
        self.assertIn("rides in slot 17's landing; keep your ticket", out[1]["text"])
        self.assertEqual({a.get("after") for a in out[1:]}, {"train:17+21+12:17"})
        self.assertNotIn("CURRENT_PLAN", out[0]["text"], "no car names a plan")

    def test_the_carrier_writes_every_cars_current_plan_as_the_trains_name(self):
        i = {s: dict(v, current=c) for (s, v), c in zip(self.I.items(), ("0131-landings", "", "owner/3/a-shot"))}
        out = trains.plan(self.Q, i, [], {}, NOW)
        self.assertIn("write `0131-landings + owner/3/a-shot` as the first line of your plans/CURRENT_PLAN",
                      out[0]["text"])

    def test_a_train_under_way_is_not_planned_again(self):
        log = [logged("train:17+21+12")]
        self.assertEqual(trains.plan(self.Q, self.I, log, {}, NOW), [])

    def test_an_old_train_no_longer_counts(self):
        log = [logged("train:17+21+12", hours_ago=13)]
        self.assertEqual(len(trains.plan(self.Q, self.I, log, {}, NOW)), 4)

    def test_failed_carrier_wakes_the_farmer(self):
        q = [ticket("17", 0, "held", holding=True, hold={"reason": "failed", "message": "test-unit hal2-git"}),
             ticket("21", 2), ticket("12", 3)]
        out = trains.plan(q, self.I, [logged("train:17+21+12")], {}, NOW)
        self.assertEqual([(a["kind"], a["do"], a["slot"]) for a in out], [("train-failed", "wake", "17")])
        self.assertIn("test-unit hal2-git", out[0]["text"])
        self.assertEqual(out[0]["train"]["passengers"], ["21", "12"])

    def test_a_held_carrier_message_holds_the_whole_train(self):
        """The carrier waits for the user: tick.fresh drops its passengers' messages and the record too."""
        log = [{"kind": "ask", "slot": "17", "at": NOW.isoformat()}]
        planned = trains.plan(self.Q, self.I, log, {}, NOW)
        self.assertEqual(tick.fresh(planned, log, NOW), [])


class PlanDone(unittest.TestCase):
    def test_no_current_plan_is_finished_and_a_shot_is_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(trains.plan_done(d))
            (Path(d) / "plans").mkdir()
            (Path(d) / "plans/CURRENT_PLAN").write_text("owner/3/some-shot\n")
            self.assertIsNone(trains.plan_done(d))
            self.assertEqual(trains.current_plan(d), "owner/3/some-shot")


if __name__ == "__main__":
    unittest.main()

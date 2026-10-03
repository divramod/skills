"""The merge-to-main boss's rules as code (subskills/merge-to-main-boss, plan 0007 step 2).

`plan(snap, ctx)` turns mtm_scan's snapshot into planned actions (see tick.py): what a rule settles is done by code,
messages are templates, and what needs judgment (a merge train, what an idle slot waits for, an unclear flaky test,
a long landing) becomes a `wake` item with the finding as evidence. Keys and windows go to tick.fresh, which drops
what an earlier round did and what concerns a slot waiting for the user. Every action carries a `key`; a key already in
the owner's log within its window is not done again, so a quiet queue gives a quiet round.
"""

import datetime as dt
import json
import sys
from pathlib import Path

import mtm_scan
from tick import act

HERE = Path(__file__).resolve().parent
BOSS = "owner (merge-to-main boss)"
SECOND_LOOK = dt.timedelta(minutes=10)  # a wake gets this long before the queue is released
REWAKE = dt.timedelta(hours=1)  # the same judgment item wakes the model at most hourly
ORPHAN = dt.timedelta(hours=3)
JUDGE = ("active-long", "work-not-queued", "long-queue", "paused")
TEXT = {
    "held-idle": BOSS + ": your failed landing holds the merge queue ({failure}). Fix the cause and rerun the "
                        "landing now (/mtm). A test that fails only under load: say so in one line.",
    "reserved-idle": BOSS + ": you reserved the merge queue for your plan's finish and nothing lands. Finish and "
                            "land now (/mtm).",
    "released": BOSS + ": your held landing did not move after a wake, so I released the merge queue. Fix it, then "
                       "/mtm again to requeue.",
    "moves": BOSS + ": the merge queue moves again ({slot} was released).",
    "priority": "merge-to-main boss: land now. The user wants slot {slot} on main first ({note}). What is "
                "committed lands; unfinished steps land after it.",
    "pause": BOSS + ": a landing runs ({slot}) and the load is high. Pause builds, tests, Docker builds and "
                    "benchmarks (/pause) until I say go.",
    "go": BOSS + ": go: /continue",
    "waiter-gone": BOSS + ": your merge-queue ticket has no live `reserve` process. Rerun `hal2-cli-git worktree "
                          "reserve --max-wait 25m --json` in a loop until it is your turn.",
}


def when(entry: dict) -> dt.datetime:
    return dt.datetime.fromisoformat(entry["at"])


def last(log: list[dict], key: str) -> dt.datetime | None:
    hits = [when(e) for e in log if e.get("key") == key]
    return max(hits) if hits else None


class Planner:
    def __init__(self, snap: dict, ctx: dict):
        self.snap, self.ctx, self.now, self.log = snap, ctx, ctx["now"], ctx["log"]
        self.wt = {w["slot"]: w for w in snap["worktrees"]}
        self.queue = snap["queue"]
        self.out: list[dict] = []

    def add(self, kind: str, do: str, slot: str = "-", window: dt.timedelta | None = None, **fields) -> None:
        if window:
            fields["window"] = window.total_seconds()
        self.out.append(act("mtm", kind, do, slot, **fields))

    def tell(self, slot: str, kind: str, text: str, key: str, window: dt.timedelta = REWAKE, **fields) -> None:
        self.add(kind, "send", slot, window, pane=self.wt.get(slot, {}).get("pane"), text=text, key=key, **fields)

    def ticket(self, slot: str) -> dict:
        return next((t for t in self.queue if t["slot"] == slot), {})

    def priority(self, f: dict) -> None:
        slot, note = f["slot"], (self.snap.get("priority") or {}).get("note") or "no reason given"
        landed = any(x["slot"] == slot and x["outcome"] == "landed" for x in self.snap["landings"])
        if landed and not self.ticket(slot) and not self.wt.get(slot, {}).get("ahead"):
            self.add("priority-done", "run", slot, argv=[sys.executable, str(HERE / "mtm_scan.py"), "priority",
                                                          "--clear", "--repo", self.ctx["main"]],
                     text=f"priority {slot} landed: cleared")
            self.add("priority-done", "notify", slot, text=f"owner: your priority slot {slot} has landed",
                     key=f"priority-done:{slot}", window=dt.timedelta(hours=1))
            return
        waiting = [t["slot"] for t in self.queue if t["state"] == "waiting"]
        if slot in waiting and waiting[0] != slot:
            self.add("front", "run", slot, argv=[sys.executable, str(HERE / "mtm_scan.py"), "front", slot,
                                                 "--repo", self.ctx["main"]], text=f"{slot} to the queue's front")
        if not self.ticket(slot):
            self.tell(slot, "priority", TEXT["priority"].format(slot=slot, note=note), f"priority:{slot}",
                      dt.timedelta(hours=6))

    def held(self, f: dict) -> None:
        slot, seq = f["slot"], self.ticket(f["slot"]).get("seq")
        key, w = f"wake:{slot}:{seq}", self.wt.get(slot, {})
        woken = last(self.log, key)
        if w.get("agent_state") is not None and woken is None:
            text = TEXT[f["kind"]].format(failure=f.get("failure") or f["why"])
            self.tell(slot, f["kind"], text, key, dt.timedelta(days=7))
            return
        if woken is not None and self.now - woken < SECOND_LOOK:
            return
        release = f"release:{slot}:{seq}"
        self.add("release", "run", slot, dt.timedelta(days=7), key=release,
                 argv=["hal2-cli-git", "worktree", "release", slot, "--json"], text=f"released the queue held by {slot}",
                 why="no session" if woken is None else "did not move after a wake")
        self.tell(slot, "released", TEXT["released"], f"released:{slot}:{seq}", dt.timedelta(days=7), after=release)
        for t in self.queue:
            if t["state"] == "waiting":
                self.tell(t["slot"], "moves", TEXT["moves"].format(slot=slot), f"moves:{slot}:{seq}:{t['slot']}",
                          after=release)

    def load_high(self, f: dict) -> None:
        landing = self.ticket(f["slot"]).get("landing")
        for slot in f.get("busy_slots", []):
            self.tell(slot, "pause", TEXT["pause"].format(slot=f["slot"]), f"pause:{landing}:{slot}",
                      dt.timedelta(days=1))

    def go(self) -> None:
        """Slots paused for a landing that no longer runs get their go."""
        head = self.queue[0] if self.queue else {}
        running = head.get("landing") if head.get("state") == "active" else None
        cutoff = self.now - dt.timedelta(hours=12)
        for e in self.log:
            key = e.get("key", "")
            if not key.startswith("pause:") or when(e) < cutoff:
                continue
            _, landing, slot = key.split(":", 2)
            if landing != str(running):
                self.tell(slot, "go", TEXT["go"], f"go:{landing}:{slot}", dt.timedelta(days=1))

    def flaky(self, f: dict) -> None:
        test, ledger = f["test"], Path(self.ctx["main"]).name
        flaky_md = mtm_scan.DATA / ledger / "flaky.md"
        if flaky_md.exists() and test in flaky_md.read_text():
            return
        load = any(test in x["tests"] and x["load_hint"] for x in self.snap["landings"])
        if load:
            self.add("flaky", "delegate", f["slot"], dt.timedelta(days=7), key=f"flaky:{test}",
                     text=f"disable the load-flaky test {test} and file its shot (urgent: it blocks landings)",
                     brief={"finding": f, "landings": [x for x in self.snap["landings"] if test in x["tests"]]})
        else:
            self.add("flaky", "wake", f["slot"], REWAKE, key=f"flaky:{test}", text=f"flaky or real? {f['why']}",
                     evidence=f)

    def orphan(self, f: dict) -> None:
        slot, w = f["slot"], self.wt.get(f["slot"], {})
        if w.get("plan") and (Path(w.get("path", "")) / "HANDOFF.md").exists():
            self.add("orphan", "run", slot, ORPHAN, key=f"orphan:{slot}",
                     argv=["hal2-cli-git", "worktree", "run", slot, "--agent", "claude", "--detach", "--prompt",
                           "/handoff c"], text=f"started a session in {slot} with /handoff c")
        else:
            self.add("orphan", "wake", slot, REWAKE, key=f"orphan:{slot}", text=f"orphaned work: {f['why']}",
                     evidence=f)

    def run(self) -> list[dict]:
        for f in self.snap["findings"]:
            kind = f["kind"]
            if kind == "priority":
                self.priority(f)
            elif kind in ("held-idle", "reserved-idle"):
                self.held(f)
            elif kind == "load-high":
                self.load_high(f)
            elif kind == "waiter-gone":
                seq = self.ticket(f["slot"]).get("seq")
                self.tell(f["slot"], kind, TEXT[kind], f"waiter:{f['slot']}:{seq}", dt.timedelta(hours=2))
            elif kind == "flaky-candidate":
                self.flaky(f)
            elif kind == "work-without-agent":
                self.orphan(f)
            elif kind in JUDGE:
                self.add(kind, "wake", f["slot"], REWAKE, key=f"{kind}:{f['slot']}", text=f["why"], evidence=f)
        self.go()
        return self.out


def plan(snap: dict, ctx: dict) -> list[dict]:
    return Planner(snap, ctx).run()


def handler(item: dict, ctx: dict) -> list[dict]:
    """duty:mtm: scan (no fetch in a dry run), keep the scan for /owner status, plan."""
    snap = mtm_scan.snapshot(ctx["top"], 24, fetch=not ctx["dry"])
    if not ctx["dry"]:
        (mtm_scan.state_dir(ctx["main"]) / "last-scan.json").write_text(json.dumps(snap, indent=1))
    return plan(snap, ctx)

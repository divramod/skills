#!/usr/bin/env python3
"""Merge trains as code (the duty `trains`, subskills/merge-train; hal2 plan 0128 step 7).

A long merge queue lands faster when finished branches that touch different files land as one: the gates run once.
`group` takes the queue's waiting tickets in queue order and, from the front, puts a finished branch (its plan done,
or no plan and commits ahead) together with the next finished ones whose changed files do not overlap any branch
already in the train, at most MAX branches. The front-most is the **carrier**: it is told (a template) to merge the
others into its branch and land as usual. The **passengers** keep their tickets (their follow-up landing is quick)
and are told to /mfm after it lands. A carrier whose landing fails while its train is under way wakes the farmer:
the train splits (judgment: which passenger broke it). Conflicts the carrier hits it resets and names itself.

  trains.py plan [--repo <dir>] [--json]
      the trains the queue allows now and the messages they would send (a dry run: nothing is sent or logged)
"""

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import mtm_scan
from tick import act, default_ref, git

HERE = Path(__file__).resolve().parent
PLAN_PY = HERE.parents[1] / "plan" / "scripts" / "plan.py"
QUEUE = ["hal2-cli-git", "worktree", "queue", "--json"]
MAX = 4  # branches per train, the carrier included
WINDOW = dt.timedelta(hours=12)  # a train under way: its slots are not grouped again, its failure is watched
TRAIN = "farmer (merge train)"
TEXT = {
    "carrier": TRAIN + ": you carry a merge train. Merge {branches} into your branch now (`git merge --no-ff "
                       "--no-edit <branch>`, one at a time; none touches a file of yours or of another), run your "
                       "quick checks and land as usual (/mtm). A merge that conflicts, or a passenger's change that "
                       "fails the landing before it lands: `git reset --hard ORIG_HEAD` for it, land without it and "
                       "name it in one line.",
    "passenger": TRAIN + ": your branch {branch} rides in slot {carrier}'s landing; keep your ticket and wait. "
                         "After it lands run /mfm; your /mtm then lands what is left (plan steps checked after the "
                         "landing), probably nothing.",
    "failed": "train {key}: the carrier {carrier}'s landing failed ({why}). Split it: find the passenger that broke "
              "it, tell the carrier to reset that merge (`git reset --hard ORIG_HEAD`) and land without it, and that "
              "passenger to land alone after /mfm.",
}


def plan_done(worktree: str) -> bool | None:
    """Whether the worktree's work is finished: its CURRENT_PLAN's plan has every step done (True/False), no
    CURRENT_PLAN (True: what is committed is the work), a shot or task name (None: unknown)."""
    current = Path(worktree) / "plans/CURRENT_PLAN"
    name = current.read_text().strip() if current.exists() else ""
    if not name:
        return True
    if not (Path(worktree) / "plans" / name / "plan.md").exists():
        return None
    try:
        p = subprocess.run([sys.executable, str(PLAN_PY), "current"], cwd=worktree, capture_output=True,
                           text=True, timeout=60)
        data = json.loads(p.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None
    return bool(data.get("total")) and data.get("done") == data.get("total")


def slot_info(main: str, tickets: list[dict]) -> dict[str, dict]:
    """Per waiting slot: finished (plan_done) and the files its branch changes against the default branch."""
    base, out = default_ref(main), {}
    for t in tickets:
        if t.get("state") != "waiting" or not t.get("worktree") or not t.get("branch"):
            continue
        files = git(main, "diff", "--name-only", f"{base}...{t['branch']}").split("\n")
        out[t["slot"]] = {"finished": plan_done(t["worktree"]) is True, "files": {f for f in files if f}}
    return out


def under_way(log: list[dict], now: dt.datetime) -> dict[str, dict]:
    """The trains recorded within WINDOW, by key: carrier, passengers, when."""
    out = {}
    for e in log:
        kind, _, cars = e.get("key", "").partition(":")
        if kind == "train" and e.get("kind") == "train" and now - dt.datetime.fromisoformat(e["at"]) < WINDOW:
            carrier, *passengers = cars.split("+")
            out[e["key"]] = {"carrier": carrier, "passengers": passengers, "at": e["at"]}
    return out


def group(tickets: list[dict], info: dict[str, dict], skip: set[str]) -> list[list[str]]:
    """Trains of slots (carrier first) from the waiting tickets in queue order."""
    free = [t["slot"] for t in sorted(tickets, key=lambda t: t.get("position", 0))
            if t.get("state") == "waiting" and not t.get("holding") and t["slot"] not in skip
            and info.get(t["slot"], {}).get("finished") and info[t["slot"]]["files"]]
    trains = []
    while free:
        cars, files = [free[0]], set(info[free[0]]["files"])
        for slot in free[1:]:
            if len(cars) == MAX:
                break
            if not info[slot]["files"] & files:
                cars.append(slot)
                files |= info[slot]["files"]
        if len(cars) > 1:
            trains.append(cars)
        free = [s for s in free if s not in cars]
    return trains


def train_actions(cars: list[str], branches: dict[str, str], panes: dict) -> list[dict]:
    """The carrier's message first; the passengers' and the record follow it (dropped with it by tick.fresh)."""
    carrier, passengers = cars[0], cars[1:]
    key, window = "train:" + "+".join(cars), WINDOW.total_seconds()
    first = f"{key}:{carrier}"
    out = [act("trains", "carrier", "send", carrier, pane=panes.get(carrier), key=first, window=window,
               text=TEXT["carrier"].format(branches=", ".join(branches[p] for p in passengers)))]
    out += [act("trains", "passenger", "send", p, pane=panes.get(p), key=f"{key}:{p}", window=window, after=first,
                text=TEXT["passenger"].format(branch=branches[p], carrier=carrier)) for p in passengers]
    return out + [act("trains", "train", "record", carrier, key=key, window=window, after=first,
                      text=f"merge train: {carrier} carries {', '.join(passengers)}")]


def failures(trains: dict[str, dict], tickets: list[dict]) -> list[dict]:
    """A train whose carrier's ticket is held by a failed landing: wake the farmer to split it."""
    held = {t["slot"]: t for t in tickets if (t.get("hold") or {}).get("reason") == "failed"}
    out = []
    for key, tr in trains.items():
        t = held.get(tr["carrier"])
        if t:
            why = (t["hold"].get("message") or t["hold"].get("step") or "failed")[:300]
            out.append(act("trains", "train-failed", "wake", tr["carrier"], key=f"{key}:failed:{t.get('seq')}",
                           text=TEXT["failed"].format(key=key, carrier=tr["carrier"], why=why), train=tr))
    return out


def plan(tickets: list[dict], info: dict[str, dict], log: list[dict], panes: dict, now: dt.datetime) -> list[dict]:
    trains = under_way(log, now)
    riding = {s for tr in trains.values() for s in [tr["carrier"], *tr["passengers"]]}
    branches = {t["slot"]: t.get("branch") or t["slot"] for t in tickets}
    out = failures(trains, tickets)
    for cars in group(tickets, info, riding):
        out += train_actions(cars, branches, panes)
    return out


def handler(item: dict, ctx: dict) -> list[dict]:
    """duty:trains: the queue, each waiting slot's state, then the trains and failed ones."""
    tickets = (mtm_scan.run_json(QUEUE, ctx["main"]) or {}).get("queue", [])
    return plan(tickets, slot_info(ctx["main"], tickets), ctx.get("log", []), ctx.get("panes", {}), ctx["now"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["plan"])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    main_dir = mtm_scan.main_checkout(args.repo)
    tickets = (mtm_scan.run_json(QUEUE, main_dir) or {}).get("queue", [])
    info = slot_info(main_dir, tickets)
    log = [json.loads(x) for x in (mtm_scan.DATA / Path(main_dir).name / "log.jsonl").read_text().splitlines()
           if x.strip()] if (mtm_scan.DATA / Path(main_dir).name / "log.jsonl").exists() else []
    actions = plan(tickets, info, log, {}, dt.datetime.now())
    if args.json:
        print(json.dumps({"slots": {s: {"finished": i["finished"], "files": len(i["files"])} for s, i in info.items()},
                          "actions": actions}, indent=1))
        return 0
    for s, i in info.items():
        print(f"{s}: {'finished' if i['finished'] else 'not finished'}, {len(i['files'])} files")
    for a in actions:
        print(f"{a['kind']} {a['slot']}: {a['text']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

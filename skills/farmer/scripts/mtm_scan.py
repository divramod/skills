#!/usr/bin/env python3
"""One snapshot of a repository's road to main, for the farmer skill's merge-to-main boss.

  scan.py scan [--repo <dir>] [--hours 24] [--json]
      the merge queue (holder, its process, its agent, attempts, why it failed),
      the waiters, the machine's load, every worktree with work not on main and
      no ticket, the failing tests of the recent landings (repeat offenders are
      flaky candidates), and findings: what the boss should act on, most urgent first
  scan.py record <kind> <slot> <what> [--note <text>]
      append what the boss did to log.jsonl (the next scans show it)
  scan.py pause|resume [--repo <dir>] [--note <why>]
      set or clear the boss's queue pause flag (sessions are told by the boss)
  scan.py summary [--repo <dir>] [--notes <text>]
      scan, then write the round's summary (queue, landings, worktrees, findings, the
      boss's actions and notes) to <main>/plans/farmer/<day>/<HHMM>.md and
      latest.md; the folder ignores itself (.gitignore `*`), so it is never committed
  scan.py priority <slot>... [--note <why>] | priority --clear
      the slots the user wants landed first (findings name them first)
  scan.py front <slot>... [--repo <dir>]
      move these waiting slots to the front of the merge queue, in this order (what the
      Merge Queue pane's drag does: ranks under the queue's flock; the head never moves)
  scan.py status [--json]
      the priority, the pause flag, the last scan, the actions of the last 6 h

Reads hal2 (hal2-cli-git worktree queue, hal2-cli-agents list), git and the recent
landings: GitHub's land.yml runs (gh) where the default branch has land.yml (mtm_ci.py),
else `hal2-cli-git worktree landings`; writes only ~/skills/farmer/<repo>/ and <main>/plans/farmer/. Exit 0 on success,
2 when a tool is missing.
"""

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import mtm_ci

DATA = Path(os.environ.get("FARMER_DIR", Path.home() / "skills/farmer"))
TOOLS = ("hal2-cli-git", "hal2-cli-agents", "git")

MINUTE = 60
HELD_IDLE_AFTER = 15 * MINUTE  # a failed landing nobody reruns
ACTIVE_TOO_LONG = 60 * MINUTE  # a landing running this long is suspect
IDLE_WITH_WORK_AFTER = 30 * MINUTE  # finished work nobody queues
LOAD_PER_CORE_HIGH = 2.0  # load average per core that breaks timing tests
BUSY = {"working", "starting"}

# Failing test names in a landing's message: Swift Testing, XCTest, cargo test, nextest.
TEST_PATTERNS = (
    re.compile(r"✘ Test (\w[\w.]*)\(.*?\) failed"),
    re.compile(r"Test Case '-\[\S+ (\w+)\]' failed"),
    re.compile(r"^\s*test ([\w:]+) \.\.\. FAILED", re.M),
    re.compile(r"FAIL \[\s*[\d.]+s\] (?:\(\d+/\d+\) )?(\S+ [\w:]+)"),
)
LOAD_HINTS = re.compile(r"busy machine|budget|watchdog|took \d|timed out|deadline|Elapsed|< .*limit", re.I)


def run(args: list[str], cwd: str | None = None) -> str:
    try:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def run_json(args: list[str], cwd: str | None = None):
    out = run(args, cwd)
    try:
        return json.loads(out) if out.strip() else None
    except json.JSONDecodeError:
        return None


def pid_alive(pid) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError):
        return False
    return True


def parse_time(text: str | None) -> float | None:
    if not text:
        return None
    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def landing_start(landing_id: str | None) -> float | None:
    """`2026-10-03T02-33-17.591Z-12` -> its start as a timestamp."""
    m = re.match(r"(\d{4}-\d\d-\d\dT)(\d\d)-(\d\d)-(\d\d(?:\.\d+)?)Z", landing_id or "")
    return parse_time(f"{m.group(1)}{m.group(2)}:{m.group(3)}:{m.group(4)}Z") if m else None


def failing_tests(message: str) -> list[str]:
    found: list[str] = []
    for pattern in TEST_PATTERNS:
        for name in pattern.findall(message or ""):
            if name not in found:
                found.append(name)
    # nextest names a test `crate::binary test_name`; cargo's own line names it bare.
    return [n for n in found if not any(o != n and o.endswith((" " + n, "::" + n)) for o in found)]


def failed_task(message: str) -> str:
    first = (message or "").splitlines()[0] if message else ""
    m = re.match(r"(\S+ [\w-]+) \(", first)
    return m.group(1) if m else first[:120]


def main_checkout(repo: str) -> str:
    common = run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], repo).strip()
    return str(Path(common).parent) if common else repo


def worktrees(main: str) -> list[dict]:
    out, items, cur = run(["git", "worktree", "list", "--porcelain"], main), [], {}
    for line in out.splitlines() + [""]:
        if not line:
            if cur.get("path") and cur.get("path") != main and not cur.get("prunable"):
                items.append(cur)
            cur = {}
        elif line.startswith("worktree "):
            cur["path"] = line[9:]
        elif line.startswith("branch "):
            cur["branch"] = line[7:].removeprefix("refs/heads/")
        elif line.startswith("prunable"):
            cur["prunable"] = True
    return items


def unmerged(path: str, default: str) -> int:
    out = run(["git", "rev-list", "--count", f"origin/{default}..HEAD"], path).strip()
    return int(out) if out.isdigit() else 0


def agents_by_checkout(agents: list[dict]) -> dict[str, dict]:
    by: dict[str, dict] = {}
    for a in agents:
        if a.get("kind") in (None, "claude", "codex", "opencode") and a.get("checkout"):
            prev = by.get(a["checkout"])
            if prev is None or a.get("state") in BUSY:
                by[a["checkout"]] = a
    return by


def landings_summary(landings: list[dict], since: float) -> tuple[list[dict], dict[str, dict]]:
    recent, tests = [], {}
    for x in landings:
        started = parse_time(x.get("started")) or 0
        if started < since:
            continue
        slot = Path(x.get("worktree") or "").name
        names = failing_tests(x.get("message") or "") if x.get("outcome") == "failed" else []
        recent.append({
            "id": x.get("id"), "slot": slot, "outcome": x.get("outcome"),
            "task": failed_task(x.get("message") or "") if x.get("outcome") != "landed" else "",
            "tests": names, "load_hint": bool(LOAD_HINTS.search(x.get("message") or "")),
        })
        for name in names:
            t = tests.setdefault(name, {"test": name, "failures": 0, "slots": []})
            t["failures"] += 1
            if slot not in t["slots"]:
                t["slots"].append(slot)
    return recent, tests


def findings(snap: dict) -> list[dict]:
    """What the boss acts on, most urgent first."""
    out, now = [], snap["now"]
    queue, by_slot = snap["queue"], {w["slot"]: w for w in snap["worktrees"]}
    head = queue[0] if queue else None
    for slot in (snap.get("priority") or {}).get("slots", []):
        w, t = by_slot.get(slot, {}), next((t for t in queue if t["slot"] == slot), None)
        place = f"#{queue.index(t)} in the queue, {t['state']}" if t else "not in the queue"
        out.append({"kind": "priority", "slot": slot,
                    "why": f"the user wants it landed first ({(snap['priority'].get('note') or '')}): {place}, "
                           f"{w.get('ahead', '?')} commits not on main, agent {w.get('agent_state') or 'none'}"})
    if snap.get("paused"):
        out.append({"kind": "paused", "slot": "", "why": f"the boss paused the queue: {snap['paused'].get('note', '')}"})
    if head and head["state"] == "held":
        age = now - (parse_time(head.get("enqueued")) or now)
        agent = by_slot.get(head["slot"], {}).get("agent_state")
        hold = head.get("hold") or {}
        # A CI landing holds the queue as its reservation while its run is tested: its process lives.
        if hold.get("reason") == "reserved" and not head.get("process_alive") and agent not in BUSY \
                and age > HELD_IDLE_AFTER:
            out.append({"kind": "reserved-idle", "slot": head["slot"],
                        "why": f"reserved the queue, its agent is {agent}, nothing lands"})
        elif hold.get("reason") != "reserved" and not head.get("process_alive") and agent not in BUSY:
            out.append({"kind": "held-idle", "slot": head["slot"],
                        "why": f"failed landing holds the queue ({hold.get('step')}, attempt "
                               f"{hold.get('attempts')}), no landing runs, its agent is {agent}",
                        "failure": failed_task(hold.get("message") or ""),
                        "tests": failing_tests(hold.get("message") or "")})
    if head and head["state"] == "active":
        if head.get("active_seconds", 0) > ACTIVE_TOO_LONG:
            f = {"kind": "active-long", "slot": head["slot"],
                 "why": f"landing {head.get('landing')} runs for {head['active_seconds'] // 60} min"}
            if snap.get("ci") and (r := mtm_ci.running_run(snap["landings"], head["slot"])):
                f["run"] = r["url"]
            out.append(f)
    if snap["load"]["per_core"] >= LOAD_PER_CORE_HIGH and head and head["state"] == "active":
        out.append({"kind": "load-high", "slot": head["slot"],
                    "why": f"load {snap['load']['load1']:.0f} on {snap['load']['cores']} cores during a landing",
                    "busy_slots": [w["slot"] for w in snap["worktrees"]
                                   if w.get("agent_state") in BUSY and w["slot"] != head["slot"]]})
    waiting = [t for t in queue if t["state"] == "waiting"]
    for t in waiting:
        if not t.get("process_alive") and not t.get("parked"):
            out.append({"kind": "waiter-gone", "slot": t["slot"], "why": "ticket without a live reserve process"})
    for name, t in sorted(snap["tests"].items(), key=lambda kv: -kv[1]["failures"]):
        if t["failures"] >= 2 or len(t["slots"]) >= 2:
            out.append({"kind": "flaky-candidate", "slot": ",".join(t["slots"]),
                        "why": f"{name} failed {t['failures']}x in {len(t['slots'])} slot(s)", "test": name})
    queued = {t["slot"] for t in queue}
    for w in snap["worktrees"]:
        if w["ahead"] and w["slot"] not in queued and w.get("agent_state") is None:
            out.append({"kind": "work-without-agent", "slot": w["slot"],
                        "why": f"{w['ahead']} commits not on main, plan {w.get('plan') or '-'}, no agent session"})
            continue
        if w["ahead"] and w["slot"] not in queued and w.get("agent_state") not in BUSY \
                and w.get("agent_idle_seconds", 0) > IDLE_WITH_WORK_AFTER:
            out.append({"kind": "work-not-queued", "slot": w["slot"],
                        "why": f"{w['ahead']} commits not on main, plan {w.get('plan') or '-'}, "
                               f"agent {w.get('agent_state') or 'none'} for {w['agent_idle_seconds'] // 60} min"})
    if len(waiting) >= 3:
        out.append({"kind": "long-queue", "slot": ",".join(t["slot"] for t in waiting),
                    "why": f"{len(waiting)} waiting: consider a merge train (see SKILL.md)"})
    return out


def snapshot(repo: str, hours: float, fetch: bool = True) -> dict:
    now = time.time()
    main = main_checkout(repo)
    default = (run(["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], main).strip()
               .removeprefix("origin/") or "main")
    if fetch:
        run(["git", "fetch", "--quiet", "origin", default], main)
    q = (run_json(["hal2-cli-git", "worktree", "queue", "--json"], main) or {}).get("queue", [])
    agents_raw = run_json(["hal2-cli-agents", "list", "--json"]) or {}
    agents = agents_raw.get("list", []) if isinstance(agents_raw, dict) else agents_raw
    by_checkout = agents_by_checkout(agents)
    ci = mtm_ci.ci_mode(run, main, default)
    if ci:
        recent, tests = mtm_ci.landings(run_json, main, now - hours * 3600), {}
    else:
        l_raw = run_json(["hal2-cli-git", "worktree", "landings", "--limit", "100", "--json"], main) or {}
        recent, tests = landings_summary(l_raw.get("landings", []), now - hours * 3600)
    queue = []
    for t in q:
        queue.append({
            "slot": t.get("slot"), "state": t.get("state"), "seq": t.get("seq"),
            "enqueued": t.get("enqueued"), "landing": t.get("landing"), "hold": t.get("hold"),
            "process_alive": pid_alive(t.get("pid")), "parked": bool(t.get("parked_until")),
            "active_seconds": int(now - (landing_start(t.get("landing")) or now)),
        })
    own = run(["git", "rev-parse", "--show-toplevel"], repo).strip()
    wts = []
    for w in worktrees(main):
        path, slot = w["path"], Path(w["path"]).name
        if slot.startswith(".") or path == own:  # hal2's own checkouts (.deliver, .bench), the farmer's slot
            continue
        a = by_checkout.get(path, {})
        plan_file = Path(path) / "plans/CURRENT_PLAN"
        since = (a.get("since") or 0) / 1000
        wts.append({
            "slot": slot, "path": path, "branch": w.get("branch"), "ahead": unmerged(path, default),
            "plan": plan_file.read_text().strip() if plan_file.exists() else "",
            "agent_state": a.get("state"), "pane": a.get("pane_id"),
            "agent_idle_seconds": int(now - since) if since and a.get("state") not in BUSY else 0,
            "context_percent": a.get("context_percent"),
        })
    load1 = os.getloadavg()[0]
    cores = os.cpu_count() or 1
    pause_file = state_dir(main) / "paused.json"
    snap = {
        "now": now, "repo": main, "default": default, "ci": ci, "queue": queue, "worktrees": wts,
        "landings": recent, "tests": tests,
        "load": {"load1": load1, "cores": cores, "per_core": round(load1 / cores, 2)},
        "paused": json.loads(pause_file.read_text()) if pause_file.exists() else None,
        "priority": json.loads(prio.read_text()) if (prio := state_dir(main) / "priority.json").exists() else None,
    }
    snap["findings"] = findings(snap)
    return snap


def queue_dir(main: str) -> Path:
    """hal2's merge queue folder: <worktree base>/.merge-queue."""
    return Path.home() / ".hal/git/worktree" / Path(main).name / ".merge-queue"


def front(main: str, slots: list[str], by: str = "the farmer's merge-to-main boss") -> list[str]:
    """hal2-git's `queue::reorder` with `slots` first: the waiting tickets get the sorted
    seqs of all waiting tickets as ranks, in the new order. Returns the waiting slots in order."""
    import fcntl
    qdir = queue_dir(main)
    with (qdir / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        waiting = []
        for f in sorted(qdir.glob("*.json")):
            try:
                t = json.loads(f.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            seq = int(f.stem)
            if t.get("state", "waiting") == "waiting" and not t.get("cancelled_by"):
                waiting.append((t.get("rank") or seq, seq, f, t))
        waiting.sort(key=lambda w: w[0])
        ranks = sorted(w[1] for w in waiting)
        named = [w for s in slots for w in waiting if w[3].get("slot") == s]
        ordered = named + [w for w in waiting if w not in named]
        for (_, seq, f, t), rank in zip(ordered, ranks):
            if (t.get("rank") or seq) != rank:
                t["rank"], t["moved_by"] = rank, by
                tmp = f.with_suffix(".tmp")
                tmp.write_text(json.dumps(t))
                tmp.replace(f)
        fcntl.flock(lock, fcntl.LOCK_UN)
    return [w[3].get("slot") for w in ordered]


def state_dir(main: str) -> Path:
    d = DATA / Path(main).name
    d.mkdir(parents=True, exist_ok=True)
    return d


LOG_FIELDS = ("kind", "slot", "what", "note")


def entries(path: Path) -> list[dict]:
    """The log's entries, tolerant of old or hand-written ones: an unreadable line or one without `at` is skipped,
    a missing kind, slot, what or note reads as "" (plan 0137: one entry without `note` crashed every tick)."""
    out = []
    for line in path.read_text().splitlines() if path.exists() else []:
        try:
            e = json.loads(line)
            dt.datetime.fromisoformat(e["at"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
        out.append({**{k: "" for k in LOG_FIELDS}, **{k: v for k, v in e.items() if v is not None}})
    return out


def log(main: str, entry: dict) -> None:
    entry = {"at": dt.datetime.now().isoformat(timespec="seconds"), **{k: "" for k in LOG_FIELDS}, **entry}
    with (state_dir(main) / "log.jsonl").open("a") as f:
        f.write(json.dumps(entry) + "\n")


def summary_dir(main: str) -> Path:
    d = Path(main) / "plans" / "farmer"
    d.mkdir(parents=True, exist_ok=True)
    ignore = d / ".gitignore"
    if not ignore.exists():
        ignore.write_text("*\n")
    return d


def actions_since(main: str, since: float) -> list[dict]:
    return [e for e in entries(state_dir(main) / "log.jsonl") if dt.datetime.fromisoformat(e["at"]).timestamp() >= since]


def render_summary(snap: dict, actions: list[dict], landings: list[dict], notes: str, lead: str = "") -> str:
    at = dt.datetime.fromtimestamp(snap["now"]).strftime("%Y-%m-%d %H:%M")
    head = snap["queue"][0] if snap["queue"] else None
    lines = [f"# farmer {at}", ""]
    lines.append(f"Load {snap['load']['load1']:.1f} on {snap['load']['cores']} cores. "
                 + (f"Queue head: {head['slot']} {head['state']}." if head else "Queue empty.")
                 + (f" Paused: {snap['paused'].get('note', '')}." if snap.get("paused") else ""))
    if notes:
        lines += ["", notes.strip()]
    if lead:
        lines += ["", "## Development lead", "", lead.strip()]
    lines += ["", "## Landings since the last summary", ""]
    lines += [f"- {l['slot']} {l['outcome']}" + (f": {l['task']}" if l["task"] else "")
              + (f" ({', '.join(l['tests'])})" if l["tests"] else "")
              + (f" {l['url']}" if l.get("url") else "") for l in landings] or ["- none"]
    lines += ["", "## Queue", ""]
    lines += [f"{i}. {t['slot']} {t['state']}" + (f" ({(t.get('hold') or {}).get('reason')}, attempt "
              f"{(t.get('hold') or {}).get('attempts')})" if t.get("hold") else "")
              for i, t in enumerate(snap["queue"])] or ["empty"]
    lines += ["", "## Findings", ""]
    lines += [f"- {f['kind']} {f['slot']}: {f['why']}" for f in snap["findings"]] or ["- none"]
    lines += ["", "## Actions", ""]
    lines += [f"- {e['at'][11:16]} {e['kind']} {e['slot']}: {e['what']}" + (f" ({e['note']})" if e.get("note") else "")
              for e in ({**{k: "" for k in LOG_FIELDS}, **a} for a in actions)] or ["- none"]
    lines += ["", "## Worktrees", "", "| slot | not on main | agent | plan |", "|---|---|---|---|"]
    lines += [f"| {w['slot']} | {w['ahead']} | {w.get('agent_state') or '-'} | {w.get('plan') or '-'} |"
              for w in snap["worktrees"] if w["ahead"] or w.get("plan")]
    return "\n".join(lines) + "\n"


def write_summary(main: str, snap: dict, notes: str, lead: str = "") -> Path:
    d = summary_dir(main)
    latest = d / "latest.md"
    since = latest.stat().st_mtime if latest.exists() else snap["now"] - 3600
    landings = [l for l in snap["landings"] if (l.get("started") or landing_start(l["id"]) or 0) >= since]
    text = render_summary(snap, actions_since(main, since), landings, notes, lead)
    stamp = dt.datetime.fromtimestamp(snap["now"])
    day = d / stamp.strftime("%Y-%m-%d")
    day.mkdir(exist_ok=True)
    path = day / f"{stamp.strftime('%H%M')}.md"
    path.write_text(text)
    latest.write_text(text)
    return path


def print_text(snap: dict) -> None:
    head = snap["queue"][0] if snap["queue"] else None
    print(f"repo {snap['repo']}  load {snap['load']['load1']:.1f}/{snap['load']['cores']} cores"
          f"  queue {len(snap['queue'])}" + (f"  head {head['slot']} {head['state']}" if head else ""))
    for f in snap["findings"]:
        print(f"- {f['kind']:16} {f['slot']:10} {f['why']}")
    if not snap["findings"]:
        print("no findings")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--repo", default=os.getcwd())
    s.add_argument("--hours", type=float, default=24)
    s.add_argument("--json", action="store_true")
    r = sub.add_parser("record")
    r.add_argument("kind")
    r.add_argument("slot")
    r.add_argument("what")
    r.add_argument("--note", default="")
    r.add_argument("--repo", default=os.getcwd())
    for name in ("pause", "resume"):
        x = sub.add_parser(name)
        x.add_argument("--repo", default=os.getcwd())
        x.add_argument("--note", default="")
    pr = sub.add_parser("priority")
    pr.add_argument("slots", nargs="*")
    pr.add_argument("--note", default="")
    pr.add_argument("--clear", action="store_true")
    pr.add_argument("--repo", default=os.getcwd())
    fr = sub.add_parser("front")
    fr.add_argument("slots", nargs="+")
    fr.add_argument("--repo", default=os.getcwd())
    sm = sub.add_parser("summary")
    sm.add_argument("--repo", default=os.getcwd())
    sm.add_argument("--hours", type=float, default=24)
    sm.add_argument("--notes", default="")
    sm.add_argument("--lead", default="", help="the development lead's part of the round")
    st = sub.add_parser("status")
    st.add_argument("--repo", default=os.getcwd())
    st.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    missing = [t for t in TOOLS if not shutil.which(t)]
    if missing:
        print(f"scan.py: missing {', '.join(missing)}; run install-prerequisites.sh", file=sys.stderr)
        return 2
    main_dir = main_checkout(args.repo)
    if args.cmd == "scan":
        snap = snapshot(args.repo, args.hours)
        (state_dir(main_dir) / "last-scan.json").write_text(json.dumps(snap, indent=1))
        print(json.dumps(snap, indent=1) if args.json else "", end="\n" if args.json else "")
        if not args.json:
            print_text(snap)
    elif args.cmd == "priority":
        f = state_dir(main_dir) / "priority.json"
        if args.clear:
            f.unlink(missing_ok=True)
        elif args.slots:
            f.write_text(json.dumps({"slots": args.slots, "note": args.note}))
        log(main_dir, {"kind": "priority", "slot": ",".join(args.slots), "what": "cleared" if args.clear else "set",
                       "note": args.note})
        print(f.read_text() if f.exists() else "no priority")
    elif args.cmd == "front":
        order = front(main_dir, args.slots)
        log(main_dir, {"kind": "front", "slot": ",".join(args.slots), "what": "moved to the front", "note": ""})
        print("waiting now: " + " ".join(order))
    elif args.cmd == "summary":
        snap = snapshot(args.repo, args.hours)
        (state_dir(main_dir) / "last-scan.json").write_text(json.dumps(snap, indent=1))
        print(write_summary(main_dir, snap, args.notes, args.lead))
    elif args.cmd == "record":
        log(main_dir, {"kind": args.kind, "slot": args.slot, "what": args.what, "note": args.note})
    elif args.cmd == "pause":
        (state_dir(main_dir) / "paused.json").write_text(
            json.dumps({"since": dt.datetime.now().isoformat(timespec="seconds"), "note": args.note}))
        log(main_dir, {"kind": "pause", "slot": "", "what": "paused", "note": args.note})
    elif args.cmd == "resume":
        (state_dir(main_dir) / "paused.json").unlink(missing_ok=True)
        log(main_dir, {"kind": "pause", "slot": "", "what": "resumed", "note": args.note})
    elif args.cmd == "status":
        d = state_dir(main_dir)
        cutoff = dt.datetime.now() - dt.timedelta(hours=6)
        recent = [e for e in entries(d / "log.jsonl") if dt.datetime.fromisoformat(e["at"]) >= cutoff]
        last = d / "last-scan.json"
        status = {
            "priority": json.loads((d / "priority.json").read_text()) if (d / "priority.json").exists() else None,
            "paused": json.loads((d / "paused.json").read_text()) if (d / "paused.json").exists() else None,
            "last_scan_age_s": int(time.time() - last.stat().st_mtime) if last.exists() else None,
            "actions_6h": recent,
        }
        print(json.dumps(status, indent=1) if args.json else
              f"paused: {status['paused']}\nlast scan: {status['last_scan_age_s']} s ago\n"
              + "\n".join(f"{e['at']} {e['kind']} {e['slot']} {e['what']} {e['note']}" for e in recent))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""The farmer's prune duty (hal2 plan 0143 step 8; the user, 2026-10-06): landed worktree slots cleaned or deleted.

  prune.py scan [--repo <dir>] [--json]
      every numbered slot 00-99 with whether it is free to prune, and why not
  prune.py clean <NN> [--repo <dir>] [--dry-run]
      a slot 00-09: checked again, then its build artifacts deleted (the cleanup skill's `delete`)
  prune.py remove <NN> [--repo <dir>] [--dry-run]
      a slot 10-99: checked again, its idle session ended (`/exit` typed only into an empty prompt, killed only when
      it does not exit: delete-worktree-session's stop.py), then `hal2-cli-git worktree remove NN --remote`

A slot is free when nothing in it is unsaved: no commit (its branch or a side branch `NN-*`) that origin's default
branch lacks, no change, no plans/CURRENT_PLAN, no merge queue ticket or boss pause, no busy agent (working,
starting, blocked), no session active in the last 30 minutes (10-99), no build running in it (cleanup's `busy`)
and no open question to the user in the farmer's log. Never main, a role slot or a name that is not two digits.
The tick (`handler`) plans a `clean` per landing (keyed on the slot's HEAD) for 00-09, one `remove` per round for
10-99, and every 6 hours the free disk and the biggest worktrees for the round summary, a notice under 100 GB free.
Exit 0 done or skipped (the slot is no longer free: prints why), 1 failed (the tick then wakes the farmer), 2 a
tool missing.
"""

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import deliver
import logstate
import mtm_scan
import tick
from tick import act

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parents[1]
CLEANUP = SKILLS / "cleanup/scripts/cleanup.py"
STOP = SKILLS / "delete-worktree-session/scripts/stop.py"
NUMBERED = re.compile(r"\d\d")
BUSY = {"working", "starting", "blocked"}
GONE = {"ended", "failed"}
QUIET = 30 * 60  # a 10-99 session active more recently is left alone
LOW_DISK_GB = 100
SIZES_EVERY = 6 * 3600  # du over every worktree takes minutes
SIZES_TOP = 5
EXIT_WAIT = 15


def git(path: str, *args: str) -> str:
    return tick.git(path, *args)


def unsaved(path: str, slot: str, base: str) -> list[str]:
    """What the slot holds that `base` (origin's default branch) lacks: commits on HEAD or a side branch, changes."""
    out = []
    ahead = git(path, "rev-list", "--count", f"{base}..HEAD")
    if ahead and ahead != "0":
        out.append(f"{ahead} commit(s) not on {base}")
    for ref in git(path, "for-each-ref", "--format=%(refname:short)", f"refs/heads/{slot}-*").split():
        n = git(path, "rev-list", "--count", f"{base}..{ref}")
        if n and n != "0":
            out.append(f"side branch {ref}: {n} commit(s) not on {base}")
    if git(path, "status", "--porcelain"):
        out.append("uncommitted changes")
    plan = Path(path) / "plans/CURRENT_PLAN"
    if plan.exists() and plan.read_text().strip():
        out.append(f"plans/CURRENT_PLAN names {plan.read_text().strip()}")
    return out


def build_running(path: str) -> bool:
    """cleanup.py's `busy`: a process whose command line names the worktree."""
    try:
        p = subprocess.run([sys.executable, str(CLEANUP), "busy", "--worktree", path], cwd=path,
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return True
    return p.returncode == 1


def sessions(agents: list[dict], path: str) -> list[dict]:
    here = Path(path).resolve()
    return [a for a in agents if a.get("checkout") and Path(a["checkout"]).resolve() == here
            and a.get("state") not in GONE]


def refusal(w: dict, ctx: dict, agents: list[dict], now_ms: float, build=build_running) -> str | None:
    """Why the slot `w` (a worktree: path, slot) may not be pruned now, None when it may."""
    slot, path = w["slot"], w["path"]
    why = unsaved(path, slot, tick.default_ref(path))
    if why:
        return "; ".join(why)
    if slot in ctx.get("waiting", set()) | ctx.get("landing", set()):
        return "it has a merge queue ticket or the boss paused it"
    if slot in logstate.waiting_for_user(ctx.get("log", [])):
        return "it waits for the user's answer"
    for a in sessions(agents, path):
        if a.get("state") in BUSY:
            return f"its agent {a.get('pane_id')} is {a['state']}"
        if int(slot) >= 10 and now_ms - (a.get("since") or 0) < QUIET * 1000:
            return f"its session {a.get('pane_id')} was active in the last {QUIET // 60} min"
    if build(path):
        return "a build or test runs in it"
    return None


def slots(main: str) -> list[dict]:
    """The repository's numbered worktree slots (path, slot, head)."""
    out = []
    for w in mtm_scan.worktrees(main):
        name = Path(w["path"]).name
        if NUMBERED.fullmatch(name):
            out.append({"path": w["path"], "slot": name, "head": git(w["path"], "rev-parse", "HEAD")})
    return sorted(out, key=lambda w: w["slot"])


def scan(main: str, ctx: dict, agents: list[dict], now_ms: float | None = None, build=build_running) -> list[dict]:
    now_ms = now_ms if now_ms is not None else time.time() * 1000
    return [{**w, "why": refusal(w, ctx, agents, now_ms, build)} for w in slots(main)]


def disk(main: str, paths: list[str], timeout: int = 300) -> dict:
    """Free disk of the main checkout's volume and the biggest worktrees (du, bounded)."""
    free = shutil.disk_usage(main).free / 1e9
    sizes = []
    try:
        out = subprocess.run(["du", "-sk", *paths], capture_output=True, text=True, timeout=timeout).stdout
        for line in out.splitlines():
            kb, _, path = line.partition("\t")
            if kb.isdigit():
                sizes.append((int(kb) / 1e6, Path(path).name))
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {"free_gb": round(free, 1), "biggest": sorted(sizes, reverse=True)[:SIZES_TOP]}


def recent(log: list[dict], prefix: str, now: dt.datetime, seconds: int) -> bool:
    return any(str(e.get("key", "")).startswith(prefix) and (now - dt.datetime.fromisoformat(e["at"])).total_seconds()
               < seconds for e in log)


def disk_actions(main: str, ctx: dict, info: dict | None) -> list[dict]:
    now = ctx["now"]
    if info is None:
        if recent(ctx.get("log", []), "prune:disk:", now, SIZES_EVERY):
            return []
        info = disk(main, [main] + [w["path"] for w in mtm_scan.worktrees(main)])
    biggest = ", ".join(f"{name} {gb:.0f} GB" for gb, name in info["biggest"]) or "unknown"
    out = [act("prune", "disk", "record", key=f"prune:disk:{now:%Y-%m-%dT%H}", window=SIZES_EVERY,
               text=f"free disk {info['free_gb']:.0f} GB; biggest worktrees: {biggest}")]
    if info["free_gb"] < LOW_DISK_GB:
        out.append(act("prune", "low-disk", "notify", key="prune:low-disk", window=SIZES_EVERY,
                       text=f"only {info['free_gb']:.0f} GB free on the disk of {main}; biggest worktrees: {biggest}"))
    return out


def failed(w: dict, what: str) -> dict:
    return act("prune", "failed", "wake", w["slot"], text=f"prune.py {what} {w['slot']} failed: see its log entry")


def plan(item: dict, ctx: dict, found: list[dict] | None = None, info: dict | None = None) -> list[dict]:
    """The prune duty's actions this round (see the module doc)."""
    main = ctx["main"]
    if found is None:
        found = scan(main, ctx, list(ctx.get("agents_by_pane", {}).values()))
    me = [sys.executable, str(HERE / "prune.py")]
    out, removed = [], False
    for w in found:
        if w["why"]:
            continue
        if int(w["slot"]) < 10:
            out.append(act("prune", "clean", "run", w["slot"], key=f"prune:clean:{w['slot']}:{w['head']}",
                           window=30 * 24 * 3600, argv=me + ["clean", w["slot"], "--repo", main],
                           text=f"clean landed slot {w['slot']}'s build artifacts", on_fail=[failed(w, "clean")]))
        elif not removed:
            removed = True
            out.append(act("prune", "remove", "run", w["slot"], key=f"prune:remove:{w['slot']}:{w['head']}",
                           window=3600, argv=me + ["remove", w["slot"], "--repo", main],
                           text=f"remove landed slot {w['slot']} with its branch (origin/{w['slot']} once merged)",
                           on_fail=[failed(w, "remove")]))
    return out + disk_actions(main, ctx, info)


def handler(item: dict, ctx: dict) -> list[dict]:
    return plan(item, ctx)


def live(main: str) -> tuple[dict, list[dict]]:
    """The tick's context (queue, pauses, log) and the agents, read now."""
    ctx = tick.context(main, main, {}, dt.datetime.now(), True)
    return ctx, list(ctx["agents_by_pane"].values())


def end_sessions(main: str, path: str, slot: str, dry: bool) -> str | None:
    """End every resting session in the slot: `/exit` into an empty prompt, stop.py when it does not exit."""
    for a in sessions(live(main)[1], path):
        pane = a["pane_id"]
        if dry:
            print(f"would end {pane} in {slot}: /exit")
            continue
        refused = deliver.send(pane, "/exit")
        if refused:
            return f"{pane}: /exit not typed: {refused}"
        end = time.monotonic() + EXIT_WAIT
        while time.monotonic() < end and sessions(live(main)[1], path):
            time.sleep(1)
        if sessions(live(main)[1], path):
            p = subprocess.run([sys.executable, str(STOP), "stop", pane, "--repo", main, "--wait", "5"],
                               capture_output=True, text=True)
            if p.returncode:
                return f"{pane} did not exit: {(p.stdout + p.stderr).strip()[-300:]}"
    return None


def act_on(main: str, slot: str, what: str, dry: bool) -> tuple[int, str]:
    w = next((x for x in slots(main) if x["slot"] == slot), None)
    if w is None:
        return 1, f"no numbered slot {slot} in {main}"
    if (what == "clean") != (int(slot) < 10):
        return 1, f"{what} is for slots {'00-09' if what == 'clean' else '10-99'}"
    ctx, agents = live(main)
    why = refusal(w, ctx, agents, time.time() * 1000)
    if why:
        return 0, f"skipped {what} {slot}: {why}"
    if what == "clean":
        argv = [sys.executable, str(CLEANUP), "delete", "--worktree", w["path"]] + (["--dry-run"] if dry else [])
        p = subprocess.run(argv, cwd=w["path"], capture_output=True, text=True)
        return p.returncode, (p.stdout + p.stderr).strip()
    problem = end_sessions(main, w["path"], slot, dry)
    if problem:
        return 0, f"skipped remove {slot}: {problem}"
    argv = ["hal2-cli-git", "worktree", "remove", slot, "--remote"]
    if dry:
        return 0, "would run " + " ".join(argv)
    code, text = tick.sh(argv, main)
    return code, text


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("cmd", choices=("scan", "clean", "remove"))
    p.add_argument("slot", nargs="?")
    p.add_argument("--repo", default=".")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    missing = [t for t in ("git", "hal2-cli-git", "hal2-cli-agents") if not shutil.which(t)]
    if missing:
        print(f"prune.py: missing {', '.join(missing)}", file=sys.stderr)
        return 2
    main_dir = mtm_scan.main_checkout(args.repo)
    if args.cmd == "scan":
        ctx, agents = live(main_dir)
        found = scan(main_dir, ctx, agents)
        print(json.dumps(found, indent=1) if args.json else
              "\n".join(f"{w['slot']}: {w['why'] or 'free'}" for w in found) or "no numbered slots")
        return 0
    if not args.slot or not NUMBERED.fullmatch(args.slot):
        print("prune.py: give a two-digit slot (00-99)", file=sys.stderr)
        return 1
    code, text = act_on(main_dir, args.slot, args.cmd, args.dry_run)
    print(text)
    return 1 if code else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

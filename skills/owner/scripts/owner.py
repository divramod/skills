#!/usr/bin/env python3
"""The owner's deterministic side: what runs without a model (.adr/deterministic-first.md, plan 0007).

  owner.py start-check [--repo <dir>] [--json]
      may the owner start here? The owner slot, holding nothing but OWNER-ROLE.md changes, the
      tools, a valid OWNER-ROLE.md; prints the loop's cron
  owner.py tick [--repo <dir>] [--dry-run] [--json]
      one round as code: stay current (merge-from-main), the user's OWNER-ROLE.md edit, what is due,
      each due item's actions, the log, the summary. Items that need judgment are collected as
      `wake`, notices for the user as `notify`. --dry-run plans the round and touches nothing.
  owner.py mode [claude|timer] [--repo <dir>]
      who runs the rounds: the owner's Claude session (`claude`, the default) or the external
      timer (`timer`). A tick without --dry-run runs only in timer mode, so the two never overlap.

State: ~/skills/owner/<repo>/ (OWNER_DIR overrides the root): mode, tick.lock, log.jsonl, runs.jsonl.
Exit 0 ok (also: another tick holds the lock, `busy`), 1 OWNER-ROLE.md invalid, 2 a tool missing,
3 no OWNER-ROLE.md, 4 not the owner slot, a slot holding other work, or not in timer mode.
"""

import argparse
import fcntl
import json
import os
import shutil
import sys
from pathlib import Path

import boss
import due
import tick

HERE = Path(__file__).resolve().parent
TOOLS = ("git", "hal2-cli-git", "hal2-cli-hooks", "hal2-cli-agents")
MODES = ("claude", "timer")
HANDLERS: dict = {  # "duty:<name>" / "task:<name>" → (item, ctx) → planned actions
    "duty:mtm": boss.handler,
}


def state(repo: str) -> Path:
    d = due.DATA / due.repo_name(repo)
    d.mkdir(parents=True, exist_ok=True)
    return d


def mode(repo: str) -> str:
    f = state(repo) / "mode"
    text = f.read_text().strip() if f.exists() else ""
    return text if text in MODES else "claude"


def start_check(repo: str) -> tuple[int, dict]:
    missing = [t for t in TOOLS if not shutil.which(t)]
    if missing:
        return 2, {"ok": False, "problems": [f"missing {', '.join(missing)}: run {HERE}/install-prerequisites.sh"]}
    problem = tick.slot_problem(repo)
    if problem:
        return 4, {"ok": False, "problems": [problem]}
    top = tick.git(repo, "rev-parse", "--show-toplevel")
    role = Path(top) / tick.ROLE
    if not role.exists():
        return 3, {"ok": False, "problems": [f"no {role}: nothing is opted in (template: templates/OWNER-ROLE.md)"]}
    items, settings, problems = due.schedule(role.read_text())
    if problems:
        return 1, {"ok": False, "problems": problems}
    return 0, {"ok": True, "loop_cron": due.loop_cron(items), "settings": settings, "mode": mode(top),
               "items": sorted(items)}


def print_round(r: dict) -> None:
    head = "dry run" if r["dry"] else "round"
    if r.get("problem"):
        print(f"owner tick ({head}): {r['problem']}")
        return
    print(f"owner tick ({head}): {len(r.get('due', []))} due"
          + (f": {', '.join(i['name'] for i in r['due'])}" if r.get("due") else ""))
    for a in r["planned"]:
        what = a.get("text") or " ".join(a.get("argv", [])) or a.get("name", "")
        print(f"- {a['do']:6} {a['duty']}/{a['kind']} {a['slot']}: {what}")
    for key in ("relay", "delegate", "wake", "notify"):
        if r.get(key):
            print(f"{key}: " + "; ".join(a.get("text", "") for a in r[key]))
    if r.get("summary"):
        print(f"summary: {r['summary']}")


def run_tick(repo: str, dry: bool, as_json: bool) -> int:
    missing = [t for t in TOOLS if not shutil.which(t)]
    if missing:
        print(f"owner.py: missing {', '.join(missing)}; run {HERE}/install-prerequisites.sh", file=sys.stderr)
        return 2
    if not dry and mode(repo) != "timer":
        print("owner.py: mode is `claude` (the owner's Claude loop runs the rounds); a tick runs only in timer mode "
              "(`owner.py mode timer`), or use --dry-run", file=sys.stderr)
        return 4
    with (state(repo) / "tick.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("busy: another tick runs")
            return 0
        r = tick.run(repo, dry, HANDLERS)
    print(json.dumps(r, indent=1, default=str) if as_json else "", end="")
    if not as_json:
        print_round(r)
    return 4 if r.get("problem") else 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sc = sub.add_parser("start-check")
    t = sub.add_parser("tick")
    t.add_argument("--dry-run", action="store_true")
    for x in (sc, t):
        x.add_argument("--repo", default=os.getcwd())
        x.add_argument("--json", action="store_true")
    m = sub.add_parser("mode")
    m.add_argument("set", nargs="?", choices=MODES)
    m.add_argument("--repo", default=os.getcwd())
    args = p.parse_args(argv)

    if args.cmd == "start-check":
        code, result = start_check(args.repo)
        print(json.dumps(result, indent=1) if args.json else
              (f"ok: loop cron `{result['loop_cron']}`, mode {result['mode']}" if result["ok"] else
               "\n".join(f"- {x}" for x in result["problems"])))
        return code
    if args.cmd == "mode":
        if args.set:
            (state(args.repo) / "mode").write_text(args.set + "\n")
        print(mode(args.repo))
        return 0
    return run_tick(args.repo, args.dry_run, args.json)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

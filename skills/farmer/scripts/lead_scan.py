#!/usr/bin/env python3
"""Which agent sessions of a repository need help, for the owner skill's development lead.

  lead_scan.py scan [--repo <dir>] [--json] [--all]
      every agent session of the repository (worktree slots and main, the owner's own
      session excluded) that waits for someone: a question to the user, a dialog or
      permission prompt, a failed turn, a session idle inside an unfinished plan, a
      context near its limit, a slot working without plans/CURRENT_PLAN; with the last thing it said. Stops already handled are
      left out (--all: shown too)
  lead_scan.py record <session-id> <since> <what> [--note <text>] [--repo <dir>]
      mark that stop handled (the next scans skip it until the session moves on)

Reads hal2-cli-agents list --json and Claude Code's transcripts; writes only
~/skills/owner/<repo>/lead.jsonl. Exit 0 on success, 2 when a tool is missing.
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

DATA = Path(os.environ.get("OWNER_DIR", Path.home() / "skills/owner"))
PROJECTS = Path(os.environ.get("CLAUDE_PROJECTS_DIR", Path.home() / ".claude/projects"))
MINUTE = 60
BLOCKED_AFTER = 5 * MINUTE
IDLE_IN_PLAN_AFTER = 20 * MINUTE
CONTEXT_HIGH = 80
WAITS_FOR_USER = re.compile(
    r"\?\s*$|waiting for (the )?user|asked the user|need(s)? (your|the user's) (answer|decision|go)"
    r"|which (one|option)|should I|do you want|let me know|confirm", re.I | re.M)


def run_json(args: list[str]):
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=60).stdout
        return json.loads(out) if out.strip() else None
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None


def main_checkout(repo: str) -> str:
    try:
        common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=repo,
                                capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        common = ""
    return str(Path(common).parent) if common else repo


def transcript(cwd: str, session_id: str) -> Path:
    return PROJECTS / re.sub(r"[/.]", "-", cwd) / f"{session_id}.jsonl"


def last_assistant_text(path: Path, max_bytes: int = 400_000) -> str:
    """The text of the transcript's last assistant message ('' when there is none)."""
    if not path.exists():
        return ""
    with path.open("rb") as f:
        size = f.seek(0, 2)
        f.seek(max(0, size - max_bytes))
        lines = f.read().decode("utf-8", "replace").splitlines()
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = entry.get("message") or {}
        if entry.get("type") != "assistant" or msg.get("role") != "assistant":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            return content.strip()
        texts = [c.get("text", "") for c in content or [] if c.get("type") == "text"]
        asks = [c for c in content or [] if c.get("type") == "tool_use" and c.get("name") == "AskUserQuestion"]
        if asks:
            qs = (asks[-1].get("input") or {}).get("questions") or []
            return "AskUserQuestion: " + " | ".join(q.get("question", "") for q in qs)
        if any(t.strip() for t in texts):
            return "\n".join(texts).strip()
    return ""


def classify(agent: dict, said: str, now: float) -> tuple[str, str] | None:
    """(kind, why) for a session that needs help, else None."""
    state, since = agent.get("state"), (agent.get("since") or 0) / 1000
    if state == "working" and agent.get("slot") not in (None, "main") and not agent.get("current_plan"):
        return "no-plan", "works without plans/CURRENT_PLAN naming its task"
    age = int(now - since) if since else 0
    if state == "blocked" and age >= BLOCKED_AFTER:
        return "blocked", f"a dialog or permission prompt waits for {age // 60} min"
    if state == "failed":
        return "failed", "its turn failed (API error, limit or crash)"
    if state in ("done", "idle", "sleeping"):
        tail = said[-600:]
        if said.startswith("AskUserQuestion") or WAITS_FOR_USER.search(tail):
            return "asks", f"waits for an answer for {age // 60} min"
        if agent.get("plan") and age >= IDLE_IN_PLAN_AFTER:
            return "idle-in-plan", f"idle for {age // 60} min inside plan {agent['plan']}"
    if (agent.get("context_percent") or 0) >= CONTEXT_HIGH and not agent.get("autoclear"):
        return "context-high", f"context at {agent['context_percent']}% with no hand-off running"
    return None


def handled(main: str) -> set[tuple[str, int]]:
    f = DATA / Path(main).name / "lead.jsonl"
    if not f.exists():
        return set()
    return {(e["session"], int(e["since"])) for e in map(json.loads, f.read_text().splitlines())}


def scan(repo: str, show_all: bool) -> dict:
    now, main = time.time(), main_checkout(repo)
    agents = run_json(["hal2-cli-agents", "list", "--json"]) or []
    agents = agents.get("list", []) if isinstance(agents, dict) else agents
    own, done = os.environ.get("CLAUDE_CODE_SESSION_ID"), handled(main)
    out = []
    for a in agents:
        if a.get("project") != main or not a.get("session_id") or a.get("session_id") == own:
            continue
        plan_file = Path(a.get("checkout") or a.get("cwd") or "/nonexistent") / "plans/CURRENT_PLAN"
        a = {**a, "current_plan": plan_file.read_text().strip() if plan_file.exists() else ""}
        said = last_assistant_text(transcript(a.get("cwd") or a.get("checkout") or "", a["session_id"]))
        hit = classify(a, said, now)
        if not hit:
            continue
        key = (a["session_id"], int(a.get("since") or 0))
        if key in done and not show_all:
            continue
        out.append({
            "kind": hit[0], "why": hit[1], "slot": a.get("slot"), "pane": a.get("pane_id"),
            "session": a["session_id"], "since": int(a.get("since") or 0), "state": a.get("state"),
            "plan": a.get("plan"), "context_percent": a.get("context_percent"), "handled": key in done,
            "said": said[-1200:],
        })
    order = {"blocked": 0, "asks": 1, "failed": 2, "idle-in-plan": 3, "context-high": 4, "no-plan": 5}
    out.sort(key=lambda x: (order[x["kind"]], x["slot"] or ""))
    return {"repo": main, "sessions": len(agents), "needs_help": out}


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--repo", default=os.getcwd())
    s.add_argument("--json", action="store_true")
    s.add_argument("--all", action="store_true")
    r = sub.add_parser("record")
    r.add_argument("session")
    r.add_argument("since", type=int)
    r.add_argument("what")
    r.add_argument("--note", default="")
    r.add_argument("--repo", default=os.getcwd())
    args = p.parse_args(argv)
    if not shutil.which("hal2-cli-agents") or not shutil.which("git"):
        print("lead_scan.py: missing hal2-cli-agents or git; run install-prerequisites.sh", file=sys.stderr)
        return 2
    if args.cmd == "scan":
        result = scan(args.repo, args.all)
        if args.json:
            print(json.dumps(result, indent=1))
        else:
            for h in result["needs_help"]:
                first = (h["said"].strip().splitlines() or [""])[-1][:140]
                print(f"- {h['kind']:13} {h['slot'] or '-':6} {h['why']}: {first}")
            if not result["needs_help"]:
                print("nobody needs help")
    else:
        d = DATA / Path(main_checkout(args.repo)).name
        d.mkdir(parents=True, exist_ok=True)
        entry = {"at": dt.datetime.now().isoformat(timespec="seconds"), "session": args.session,
                 "since": args.since, "what": args.what, "note": args.note}
        with (d / "lead.jsonl").open("a") as f:
            f.write(json.dumps(entry) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

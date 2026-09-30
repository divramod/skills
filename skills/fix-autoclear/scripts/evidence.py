#!/usr/bin/env python3
"""Collect what hal2's autoclear left behind, for the fix-autoclear skill.

  evidence.py show [--pane %46] [--session <id>] [--worktree <NN|dir>] [--hours 3]
      one incident: the pane's job record and log, the guard markers of its
      sessions, each session's transcript tail (tools, hook denials, the typed
      requests), the sweep's lines from hal2-api.log, the settings and binary
  evidence.py doctor [--hours 24]
      every pane's failed or stuck autoclear of the last hours (nobody reported)
  evidence.py selfcheck [--repo <hal2 checkout>]
      whether the insider facts in SKILL.md still match hal2's code

Exit 0 on success, 1 when selfcheck finds drift, 2 when a tool is missing.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
STATE = Path(os.environ.get("HAL2_STATE_ROOT", HOME / ".local/state/hal2"))
JOBS = STATE / "agents" / "autoclear"
API_LOG = HOME / "Library/Logs/hal2-api.log"
PROJECTS = HOME / ".claude/projects"
SKILL_MD = Path(__file__).resolve().parent.parent / "SKILL.md"
SRC = "code/rust/libs/hal2-agents/src"


def need(tool):
    if shutil.which(tool) is None:
        print(f"evidence.py: missing {tool}; run scripts/install-prerequisites.sh", file=sys.stderr)
        sys.exit(2)


def stamp(ms):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ms / 1000)) if ms else "-"


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def agents():
    need("hal2-cli-agents")
    out = subprocess.run(["hal2-cli-agents", "list", "--json"], capture_output=True, text=True)
    try:
        data = json.loads(out.stdout)
    except ValueError:
        return []
    return data if isinstance(data, list) else data.get("agents", [])


def markers():
    """Every guard marker, newest first."""
    found = [(p, read_json(p)) for p in JOBS.glob("*.guard")]
    found = [(p, m) for p, m in found if m]
    return sorted(found, key=lambda pm: pm[0].stat().st_mtime, reverse=True)


def pane_stem(pane):
    return pane.lstrip("%").removeprefix("t:")


def transcript(session):
    hits = list(PROJECTS.glob(f"*/{session}.jsonl"))
    return hits[0] if hits else None


def transcript_tail(path, entries=30):
    """The last tool calls, results, hook denials and typed prompts."""
    lines = []
    for raw in path.read_text(errors="replace").splitlines():
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        ts = (d.get("timestamp") or "")[11:19]
        att = d.get("attachment") or {}
        if att.get("type") == "hook_stopped_continuation":
            lines.append(f"{ts} HOOK-STOP {att.get('message', '')[:200]}")
        msg = d.get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            lines.append(f"{ts} {msg.get('role')} {content[:300]}")
            continue
        for block in content if isinstance(content, list) else []:
            kind = block.get("type")
            if kind == "tool_use":
                lines.append(f"{ts} TOOL {block['name']} {json.dumps(block.get('input'))[:500]}")
            elif kind == "tool_result":
                text = str(block.get("content"))
                if "hook" in text.lower() or block.get("is_error"):
                    lines.append(f"{ts} RESULT {text[:300]}")
            elif kind == "text" and msg.get("role") == "assistant":
                lines.append(f"{ts} SAID {block['text'][:200]}")
    return lines[-entries:]


def sweep_lines(pane, hours):
    if not API_LOG.exists():
        return [f"(no {API_LOG})"]
    since = time.time() - hours * 3600
    keep = []
    for line in API_LOG.read_text(errors="replace").splitlines():
        if "sweep" not in line:
            continue
        if pane and pane not in line and "acted on" not in line:
            continue
        m = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)", line)
        if m and time.mktime(time.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S")) - time.timezone < since:
            continue
        keep.append(line)
    acted = [l for l in keep if "acted on" not in l or " 0 acted on" not in l]
    return acted[-15:] or keep[-3:]


def own_log(name, needles, hours, keep=40):
    """The lines of `<jobs>/<name>` (and its rotated `.1`) of the last hours
    that contain one of `needles` (all lines when `needles` is empty)."""
    since = time.time() - hours * 3600
    lines = []
    for path in (JOBS / f"{name}.1", JOBS / name):
        if not path.exists():
            continue
        for line in path.read_text(errors="replace").splitlines():
            m = re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)", line)
            if m and time.mktime(time.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")) < since:
                continue
            if not needles or any(n and n in line for n in needles):
                lines.append(line)
    return lines[-keep:] or [f"(nothing in {JOBS / name} for {', '.join(filter(None, needles)) or 'the period'})"]


def resolve_pane(args):
    if args.pane:
        return args.pane
    if args.session:
        for _, m in markers():
            if m.get("session_id") == args.session and m.get("pane"):
                return m["pane"]
    if args.worktree:
        wt = args.worktree
        for a in agents():
            checkout = a.get("checkout") or ""
            if a.get("slot") == wt or checkout.rstrip("/").endswith("/" + wt) or checkout == wt:
                if a.get("kind") == "claude":
                    return a.get("pane_id")
    return None


def show(args):
    pane = resolve_pane(args)
    print(f"# autoclear evidence ({time.strftime('%Y-%m-%d %H:%M:%S')})\n")
    need("hal2-cli-agents")
    settings = subprocess.run(["hal2-cli-agents", "settings"], capture_output=True, text=True).stdout
    binary = shutil.which("hal2-cli-agents") or "hal2-cli-agents"
    print(f"## settings\n{settings.strip()}\nbinary {binary}, built {stamp(os.path.getmtime(binary) * 1000)}\n")
    if not pane:
        print("no pane found: pass --pane, --session or --worktree")
        return
    agent = next((a for a in agents() if a.get("pane_id") == pane), None)
    if agent:
        keys = ["checkout", "slot", "plan", "state", "context_percent", "session_id", "autoclear"]
        print("## agent now\n" + json.dumps({k: agent.get(k) for k in keys}, indent=1) + "\n")
    stem = pane_stem(pane)
    print(f"## job {JOBS / (stem + '.json')}\n{json.dumps(read_json(JOBS / (stem + '.json')), indent=1)}\n")
    log = JOBS / f"{stem}.log"
    if log.exists():
        print(f"## job log (last 40 lines)\n" + "\n".join(log.read_text().splitlines()[-40:]) + "\n")
    since = time.time() - args.hours * 3600
    sessions = []
    for path, m in markers():
        if m.get("pane") == pane and path.stat().st_mtime >= since:
            print(f"## marker {path.name}\n{json.dumps(m)}  (soft {stamp(m.get('soft_at'))}, hard {stamp(m.get('hard_at'))})\n")
            sessions.append(m["session_id"])
    if args.session and args.session not in sessions:
        sessions.insert(0, args.session)
    for session in sessions[:3]:
        path = transcript(session)
        if path:
            print(f"## transcript {path}\n" + "\n".join(transcript_tail(path)) + "\n")
    print("## guard decisions (guard.log)\n" + "\n".join(own_log("guard.log", [pane] + sessions, args.hours)) + "\n")
    print("## sweep rounds for the pane (sweep.log)\n" + "\n".join(own_log("sweep.log", [f" {pane} "], args.hours, 20)) + "\n")
    print("## sweep (hal2-api.log)\n" + "\n".join(sweep_lines(pane, args.hours)))


def doctor(args):
    since = time.time() - args.hours * 3600
    problems = 0
    for record in sorted(JOBS.glob("*.json")):
        job = read_json(record)
        if not job or record.stat().st_mtime < since:
            continue
        if job.get("state") in ("failed",) or (
            job.get("state") in ("waiting", "requesting") and time.time() - record.stat().st_mtime > 1800
        ):
            problems += 1
            print(f"{job.get('pane')}: {job.get('state')} {job.get('reason') or ''} {job.get('message') or ''} "
                  f"({stamp(job.get('updated_at'))})")
    for path, m in markers():
        if path.stat().st_mtime >= since and (m.get("gave_up") or m.get("attempts", 0) >= 2):
            problems += 1
            print(f"{m.get('pane')}: session {m['session_id']} attempts {m.get('attempts', 0)}"
                  f"{' gave up' if m.get('gave_up') else ''}")
    print(f"{problems} problem(s) in the last {args.hours} h")


def selfcheck(args):
    """Every `path` and every `name` in SKILL.md's insider table must still exist."""
    repo = Path(args.repo).expanduser()
    skill = SKILL_MD.read_text()
    drift = []
    for rel in sorted(set(re.findall(r"`((?:code|\.hal|docs|research|plans)/[^`\s]+?)`", skill))):
        if "<" not in rel and "*" not in rel and not (repo / rel).exists():
            drift.append(f"missing path {rel}")
    source = "\n".join(p.read_text() for p in (repo / SRC).glob("*.rs")) if (repo / SRC).exists() else ""
    block = skill.split("<!-- names -->")[1].split("<!-- /names -->")[0] if "<!-- names -->" in skill else ""
    for name in re.findall(r"`([a-z][a-z-]+)`", block):
        if f'"{name}"' not in source:
            drift.append(f"name `{name}` no longer in {SRC}")
    for fact in re.findall(r"`(REARM_POINTS|MAX_ATTEMPTS|DEFAULT_PROMPT|HANDOFF_PROGRAMS|HANDOFF_SCRIPTS)`", skill):
        if fact not in source:
            drift.append(f"constant {fact} no longer in {SRC}")
    hooks = (HOME / ".claude/settings.json").read_text() if (HOME / ".claude/settings.json").exists() else ""
    if "hal2-cli-agents hook claude PreToolUse" not in hooks:
        drift.append("~/.claude/settings.json has no PreToolUse hook: run hal2-cli-agents install-hooks claude")
    for line in drift:
        print("DRIFT", line)
    print("ok" if not drift else f"{len(drift)} drift(s): update SKILL.md (Insider knowledge) to match")
    return 1 if drift else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show")
    s.add_argument("--pane")
    s.add_argument("--session")
    s.add_argument("--worktree")
    s.add_argument("--hours", type=float, default=3)
    d = sub.add_parser("doctor")
    d.add_argument("--hours", type=float, default=24)
    c = sub.add_parser("selfcheck")
    c.add_argument("--repo", default="~/a/hal2")
    args = parser.parse_args()
    if args.cmd == "show":
        show(args)
    elif args.cmd == "doctor":
        doctor(args)
    else:
        sys.exit(selfcheck(args))


if __name__ == "__main__":
    main()

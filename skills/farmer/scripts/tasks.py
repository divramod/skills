"""OWNER-ROLE.md tasks the tick runs itself (plan 0007 step 5).

A task is **machine-run** when its lines are in the strict form:

  - **Check**: `<command>` [and `<command>` ...]      every command exits 0: fine
  - **Act**: `<command>`, ..., notify, delegate        run in order, then the Check again
  - **Still failing**: notify, delegate                after the Act's recheck (default: notify)

Commands run with `sh -c` in the main checkout; `owner <args>` runs this skill's owner.py. Act's keywords are
`notify` (tell the user, batched), `delegate` (a worker fixes it, the failing check's output as evidence) and `wake`
(the owner's model decides). Anything else on those lines, any prose, makes the task the model's: it wakes the
owner with the task's text. So a task written before this form never runs a command by accident.
"""

import re
import subprocess
import sys
from pathlib import Path

from tick import act

OWNER = [sys.executable, str(Path(__file__).resolve().parent / "owner.py")]
CMD = r"`([^`]+)`"
CHECK = re.compile(rf"^{CMD}(?:\s*(?:,|and|&&)\s*{CMD})*\.?$")
KEYWORDS = ("notify", "delegate", "wake")


def field(block: str, name: str) -> str | None:
    m = re.search(rf"^\s*-\s*\*\*{name}\*\*:\s*(.+?)\s*$", block, re.M)
    return m.group(1) if m else None


def steps(text: str | None) -> list[tuple[str, str]] | None:
    """`a`, notify → [("run", "a"), ("notify", "")]; None when the line is not in the strict form."""
    if not text:
        return None
    out = []
    for part in re.split(r"\s*[,;]\s*", text.strip().rstrip(".")):
        m = re.fullmatch(CMD, part)
        if m:
            out.append(("run", m.group(1)))
        elif part in KEYWORDS:
            out.append((part, ""))
        else:
            return None
    return out


def parse(role_text: str) -> dict[str, dict]:
    """Every task under `## Tasks`: {name: {machine, check, act, still, text}}."""
    body = role_text.split("\n## Tasks", 1)
    if len(body) < 2:
        return {}
    section, out = re.split(r"\n## (?!#)", body[1], maxsplit=1)[0], {}
    for block in re.split(r"\n### ", "\n" + section)[1:]:
        name, check_line = block.splitlines()[0].strip(), field(block, "Check") or ""
        check = re.findall(CMD, check_line) if CHECK.match(check_line) else None
        act_steps, still = steps(field(block, "Act")), steps(field(block, "Still failing")) or [("notify", "")]
        machine = bool(check) and bool(act_steps) and all(k != "run" or v for k, v in still)
        out[name] = {"machine": machine, "check": check, "act": act_steps, "still": still, "text": block.strip()}
    return out


def argv(cmd: str, top: str) -> list[str]:
    return OWNER + cmd.split()[1:] + ["--repo", top] if cmd.split()[0] == "owner" else ["sh", "-c", cmd]


def run_check(cmds: list[str], top: str, main: str) -> tuple[bool, str]:
    for cmd in cmds:
        try:
            p = subprocess.run(argv(cmd, top), cwd=main, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            return False, f"{cmd}: timed out after 120 s"
        if p.returncode:
            return False, f"{cmd}: exit {p.returncode}\n{(p.stdout + p.stderr)[-1500:]}"
    return True, ""


def outcome(kind: str, name: str, why: str) -> dict:
    if kind == "delegate":
        return act("task", name, "delegate", key=f"task:{name}", window=86400, text=f"task {name}: {why.splitlines()[0]}",
                   brief={"task": name, "check": why})
    if kind == "notify":
        return act("task", name, "notify", key=f"task-notify:{name}", window=3600, text=f"owner task {name}: {why[:300]}")
    return act("task", name, "wake", key=f"task-wake:{name}", window=3600, text=f"task {name}: {why[:300]}")


def plan_task(item: dict, ctx: dict, specs: dict | None = None, check=run_check) -> list[dict]:
    name = item["name"].split(":", 1)[1]
    spec = (specs if specs is not None else parse((Path(ctx["top"]) / "OWNER-ROLE.md").read_text())).get(name)
    if not spec or not spec["machine"]:
        return [act("task", name, "wake", key=f"task-wake:{name}", window=3600,
                    text=f"task {name}: not in the machine form, run it as written", evidence=spec and spec["text"])]
    ok, why = check(spec["check"], ctx["top"], ctx["main"])
    if ok:
        return [act("task", name, "record", text=f"task {name}: check passed")]
    out, recheck = [], None
    for kind, cmd in spec["act"]:
        if kind == "run":
            out.append(act("task", name, "run", argv=argv(cmd, ctx["top"]), cwd=ctx["main"], why=why.splitlines()[0],
                           key=f"task-act:{name}", window=1800, text=f"task {name}: {cmd}"))
            recheck = True
        else:
            out.append(outcome(kind, name, why))
    if recheck:
        out.append(act("task", name, "run", argv=OWNER + ["check", "task", name, "--repo", ctx["top"]], cwd=ctx["main"],
                       text=f"task {name}: check again",
                       on_fail=[outcome(k, name, "still failing after the act") for k, _ in spec["still"]]))
    return out


def flaky_open(main: str, slots: dict[str, dict]) -> list[str]:
    """Ledger entries not back yet whose worker slot runs no plan any more."""
    import mtm_scan
    f = mtm_scan.DATA / Path(main).name / "flaky.md"
    out = []
    for line in (f.read_text().splitlines() if f.exists() else []):
        if not line.startswith("- "):
            continue
        status = line.rsplit(" · ", 1)[-1]
        m = re.match(r"running \((\d+)", status)
        if status.startswith("landed") or (m and slots.get(m.group(1), {}).get("plan")):
            continue
        out.append(line[2:200])
    return out


def orphans(top: str) -> list[dict]:
    """mtm_scan's work-without-agent findings, without the slots that wait for the user."""
    import mtm_scan
    import tick
    snap = mtm_scan.snapshot(top, 24, fetch=False)
    asked = tick.waiting_for_user(tick.read_log(snap["repo"]))
    return [f for f in snap["findings"] if f["kind"] == "work-without-agent" and f["slot"] not in asked]


def builtin(what: str, top: str) -> tuple[int, str]:
    """`owner check task <name>|flaky|orphans`: exit 0 when fine, 1 with what is wrong."""
    import mtm_scan
    import tick
    main = mtm_scan.main_checkout(top)
    if what == "flaky":
        bad = flaky_open(main, tick.slot_state(main))
    elif what == "orphans":
        bad = [f"{f['slot']}: {f['why']}" for f in orphans(top)]
    else:
        spec = parse((Path(top) / "OWNER-ROLE.md").read_text()).get(what)
        if not spec or not spec["check"]:
            return 2, f"no machine-run task {what!r}"
        ok, why = run_check(spec["check"], top, main)
        bad = [] if ok else [why]
    return (1 if bad else 0), "\n".join(bad)

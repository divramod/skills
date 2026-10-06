"""Parallel plans (skills plan 0013; hal2 02's one-plan-answer.md, section D): a step table with the columns
`| # | Step | Needs | Touches | Who | Done when | Status |` runs its steps in parallel.

- Needs: comma-separated step ids and ranges (`3-7`); blank or `-` is none. Ids are integers, never renumbered.
- Touches: comma-separated resources (`rust:<crate>`, `ts:<package>`, `proto:<package>`, `docs`, `@hub-stack`, ...);
  two steps sharing one never run at once. Each resource has room for one step, `@vm` for two; a `Capacity:` line
  under the title (`Capacity: @vm=2, @x=3`) overrides. A row whose Step starts with `Milestone <n>` touches `@land`.
- Who: `lead`, `subagent`, `user` or `slot NN` (a subservant in worktree slot 30-99).
- Status: `done...`, `running`, `blocked <why>`, anything else (blank, `next`) is open.

A subservant's slot holds the gitignored marker `plans/LEAD`, one line `<lead-slot> <plan-slug> <step>`.
"""
import re
import subprocess
from pathlib import Path

LEAD = Path("plans") / "LEAD"
DEFAULT_CAPACITY = {"@vm": 2}
MILESTONE = re.compile(r"^\W*milestone\s+\d+", re.I)
WHO = re.compile(r"^(lead|subagent|user|slot (\d\d))$")
SUBSERVANT_SLOTS = range(30, 100)
TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


class ParallelError(Exception):
    pass


def is_parallel(cols: dict[str, int]) -> bool:
    return "needs" in cols


def parse_needs(text: str) -> tuple[list[str], list[str]]:
    """(step ids, tokens that are no id or range)."""
    ids, bad = [], []
    for token in (t.strip() for t in text.split(",")):
        if token in ("", "-", "—"):
            continue
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", token)
        if m and int(m.group(1)) <= int(m.group(2)):
            ids += [str(n) for n in range(int(m.group(1)), int(m.group(2)) + 1)]
        elif token.isdigit():
            ids.append(str(int(token)))
        else:
            bad.append(token)
    return ids, bad


def parse_touches(text: str, step: str = "") -> list[str]:
    touches = [t.strip() for t in text.split(",") if t.strip() not in ("", "-", "—")]
    if MILESTONE.match(step) and "@land" not in touches:
        touches.append("@land")
    return touches


def kind(status: str) -> str:
    s = status.lower().lstrip("*_ ")
    for k in ("done", "running", "blocked"):
        if s.startswith(k):
            return k
    return "open"


def capacity(text: str) -> dict[str, int]:
    """Room per resource: 1, `@vm` 2, and what a `Capacity: @x=3, ...` line above the first section says."""
    room = dict(DEFAULT_CAPACITY)
    for line in text.splitlines():
        if line.startswith("## "):
            break
        if line.startswith("Capacity:"):
            for part in line.split(":", 1)[1].split(","):
                name, _, n = part.partition("=")
                if name.strip() and n.strip().isdigit():
                    room[name.strip()] = int(n)
    return room


def enrich(step: dict, cells: list[str], cols: dict[str, int]) -> None:
    """Add a parallel row's needs, touches and who to its step dict."""
    cell = lambda name: cells[cols[name]] if name in cols else ""  # noqa: E731
    step["needs"], step["bad_needs"] = parse_needs(cell("needs"))
    step["touches"] = parse_touches(cell("touches"), step["step"])
    step["who"] = cell("who")


def problems(steps: list[dict]) -> list[str]:
    """Ids that are no integer or used twice, Needs no row has, and cycles."""
    out, ids, seen = [], [s["number"] for s in steps], set()
    for s in steps:
        if not s["number"].isdigit():
            out.append(f"step id '{s['number']}' is no integer: a parallel plan's ids are integers, never renumbered")
        elif s["number"] in seen:
            out.append(f"step id '{s['number']}' is used twice")
        seen.add(s["number"])
        if s["bad_needs"]:
            out.append(f"step {s['number']}: Needs '{', '.join(s['bad_needs'])}' are no step ids or ranges")
        missing = [n for n in s["needs"] if n not in ids]
        if missing:
            out.append(f"step {s['number']} needs step(s) {', '.join(missing)}, which no row has")
    needs = {s["number"]: [n for n in s["needs"] if n in ids] for s in steps}
    state: dict[str, int] = {}

    def visit(n: str, path: list[str]) -> list[str] | None:
        state[n] = 1
        for m in needs.get(n, []):
            if state.get(m) == 1:
                return path + [n, m]
            if not state.get(m) and (cycle := visit(m, path + [n])):
                return cycle
        state[n] = 2
        return None

    for s in steps:
        if not state.get(s["number"]) and (cycle := visit(s["number"], [])):
            start = cycle.index(cycle[-1])
            out.append(f"the Needs form a cycle: {' -> '.join(cycle[start:])}")
            break
    return out


def schedule(steps: list[dict], room: dict[str, int], limit: int | None = None) -> tuple[list[dict], list[dict]]:
    """(ready, waiting): ready steps picked greedily in table order, each open one left over with why it waits."""
    done = {s["number"] for s in steps if kind(s["status"]) == "done"}
    used: dict[str, int] = {}
    for s in steps:
        if kind(s["status"]) == "running":
            for t in s["touches"]:
                used[t] = used.get(t, 0) + 1
    ready, waiting = [], []
    for s in steps:
        if kind(s["status"]) != "open":
            continue
        open_needs = [n for n in s["needs"] if n not in done]
        busy = [t for t in s["touches"] if used.get(t, 0) >= room.get(t, 1)]
        if s["after_landing"]:
            why = "checked after the landing"
        elif open_needs:
            why = f"needs step(s) {', '.join(open_needs)}"
        elif busy:
            why = f"touches {', '.join(busy)}, in use"
        elif limit is not None and len(ready) >= limit:
            why = f"the limit of {limit} is reached"
        else:
            ready.append(s)
            for t in s["touches"]:
                used[t] = used.get(t, 0) + 1
            continue
        waiting.append({"number": s["number"], "step": s["step"], "why": why})
    return ready, waiting


def check_who(who: str) -> str:
    who = " ".join(who.split()).lower()
    m = WHO.match(who)
    if not m:
        raise ParallelError(f"who '{who}' is none of lead, subagent, user, slot NN")
    if m.group(2) and int(m.group(2)) not in SUBSERVANT_SLOTS:
        raise ParallelError(f"{who}: subservants work only in slots 30-99")
    return who


def slot_of(who: str) -> str | None:
    m = WHO.match(who)
    return m.group(2) if m else None


def read_marker(root: Path) -> dict | None:
    """The subservant marker `plans/LEAD`: {slot, plan, step}, None when there is none."""
    f = root / LEAD
    if not f.is_file():
        return None
    parts = f.read_text().split()
    if len(parts) < 3:
        raise ParallelError(f"{LEAD} must hold `<lead-slot> <plan> <step>`, not '{f.read_text().strip()}'")
    return {"slot": parts[0], "plan": parts[1], "step": parts[2]}


def write_marker(worktree: Path, lead: str, plan: str, step: str) -> Path:
    (worktree / "plans").mkdir(exist_ok=True)
    (worktree / LEAD).write_text(f"{lead} {plan} {step}\n")
    (worktree / "plans" / "CURRENT_PLAN").write_text(plan + "\n")
    return worktree / LEAD


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)


def slot_worktree(root: Path, slot: str) -> Path | None:
    """The worktree of slot `slot` of this repository (a checkout named NN), None when there is none."""
    out = git(root, "worktree", "list", "--porcelain").stdout
    for line in out.splitlines():
        if line.startswith("worktree ") and Path(line[9:]).name == slot:
            return Path(line[9:])
    return None


def fill(template: str, **fields: str) -> str:
    return (TEMPLATES / template).read_text().format(**fields)


def brief_prompt(slug: str, step: str, lead: str) -> str:
    return (f"You are a subservant of plan {slug}, step {step} only, for the lead in slot {lead}. Never ask the user "
            f"anything. Read your brief plans/{slug}/steps/{step}.md (merge origin/{lead} first when it is missing) "
            f"and do that one step as its rules say: commit with `(plan {slug[:4]} step {step})`, write your report "
            f"with the plan skill's `plan.py report {step}`, push your branch, tell the session in slot {lead}. Never "
            f"edit plan.md, never land, never run another step.")


def arrived(root: Path, slug: str, steps: list[dict], fetch: bool = True) -> list[dict]:
    """The running `slot NN` steps whose report `plans/<slug>/reports/<n>.md` is on origin/NN."""
    out = []
    for s in steps:
        slot = slot_of(s.get("who", "").lower())
        if kind(s["status"]) != "running" or not slot:
            continue
        if fetch:
            git(root, "fetch", "--quiet", "origin", f"+refs/heads/{slot}:refs/remotes/origin/{slot}")
        report = f"plans/{slug}/reports/{s['number']}.md"
        if git(root, "cat-file", "-e", f"origin/{slot}:{report}").returncode == 0:
            sha = git(root, "rev-parse", "--short", f"origin/{slot}").stdout.strip()
            out.append({"number": s["number"], "step": s["step"], "slot": slot, "sha": sha, "report": report})
    return out

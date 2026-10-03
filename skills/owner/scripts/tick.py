"""The owner's round frame as code: what `owner.py tick` plans and does each round.

A round is planned as actions (plain dicts), then carried out by `execute`, so a dry run plans the same
round and does nothing. An action:

  {"duty": "frame"|<duty>|"task", "kind": <what>, "slot": <slot or "-">, "do": <how>, ...}

with `do` one of
  run     argv: run a command (the result decides follow-ups, see `stay_current`)
  ran     name: due.py's run record for a duty or task
  record  text: a log line only
  wake    text: an item that needs the model (step 6 hands these to the woken session)
  notify  text: a notice for the user (the woken session pushes them, batched)

Every executed action except `ran` goes into the owner's log with `"by": "tick"`.
"""

import datetime as dt
import json
import subprocess
from pathlib import Path

import due
import mtm_scan

OWNER_SLOT = "owner"
ROLE = "OWNER-ROLE.md"
MFM = ["hal2-cli-git", "worktree", "merge-from-main", "--json"]


def sh(argv: list[str], cwd: str, timeout: int = 900) -> tuple[int, str]:
    try:
        p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, str(e)


def git(repo: str, *args: str) -> str:
    """git's stdout (leading whitespace kept: porcelain status columns), "" on failure."""
    try:
        p = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return p.stdout.rstrip("\n") if p.returncode == 0 else ""


def default_ref(repo: str) -> str:
    return git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD") or "origin/main"


def slot_problem(repo: str) -> str | None:
    """None when `repo` is the owner slot holding nothing but OWNER-ROLE.md changes, else why not."""
    top = git(repo, "rev-parse", "--show-toplevel")
    if not top or Path(top).name != OWNER_SLOT:
        return f"not the owner slot ({top or repo}): start me with `hal2-cli-git worktree run owner --agent claude`"
    changed = set(git(top, "diff", "--name-only", f"{default_ref(top)}...HEAD").split())
    changed |= {line[3:].strip() for line in git(top, "status", "--porcelain").splitlines()}
    other = sorted(changed - {ROLE, ""})
    return f"the owner slot holds more than {ROLE}: {', '.join(other)}" if other else None


def act(duty: str, kind: str, do: str, slot: str = "-", **fields) -> dict:
    return {"duty": duty, "kind": kind, "slot": slot, "do": do, **fields}


def role_edit(top: str) -> tuple[list[dict], bool]:
    """The user's uncommitted OWNER-ROLE.md edit: commit it when valid. Returns (actions, round may go on)."""
    if not git(top, "status", "--porcelain", "--", ROLE):
        return [], True
    path = Path(top) / ROLE
    if not path.exists():
        return [act("frame", "role-gone", "notify", text=f"{ROLE} was deleted in the owner slot: nothing runs")], False
    problems = due.schedule(path.read_text())[2]
    if problems:
        return [act("frame", "role-invalid", "notify",
                    text=f"{ROLE} edit not committed, nothing runs: " + "; ".join(problems))], False
    return [act("frame", "role-commit", "run", argv=["git", "commit", "-q", "-m", "owner-role: the user's change",
                                                    "--", ROLE], text=f"committed the user's {ROLE} edit")], True


def due_items(top: str, now: dt.datetime | None = None) -> tuple[list[dict], dict, list[str]]:
    """(the due duties and tasks, the settings, problems) from the slot's OWNER-ROLE.md."""
    path = Path(top) / ROLE
    if not path.exists():
        return [], {}, [f"no {ROLE}: nothing is opted in"]
    items, settings, problems = due.schedule(path.read_text())
    if problems:
        return [], settings, problems
    now, last = now or dt.datetime.now(), due.last_runs(top)
    rows = [{"name": n, "cron": c, "last": last[n].isoformat() if n in last else None}
            for n, c in items.items() if due.is_due(c, last.get(n), now)]
    return rows, settings, []


def item_actions(item: dict, handlers: dict) -> list[dict]:
    """The planned actions of one due duty or task, ending with its run record."""
    kind, _, name = item["name"].partition(":")
    handler = handlers.get(item["name"])
    planned = handler(item) if handler else [
        act(name if kind == "duty" else "task", "no-handler", "wake",
            text=f"{item['name']} has no tick handler yet: run it as the skill says")]
    return planned + [act(name if kind == "duty" else "task", "ran", "ran", name=item["name"])]


def plan_round(top: str, handlers: dict, now: dt.datetime | None = None) -> dict:
    """Plan everything after the frame's git work: the due items and their actions."""
    items, settings, problems = due_items(top, now)
    if problems:
        return {"due": [], "settings": settings, "actions": [act("frame", "role-invalid", "notify",
                                                                 text="; ".join(problems))], "stop": True}
    actions = [a for item in items for a in item_actions(item, handlers)]
    return {"due": items, "settings": settings, "actions": actions, "stop": False}


def execute(a: dict, top: str, main: str, out: dict) -> None:
    """Carry out one planned action; wake and notify items are collected in `out`."""
    if a["do"] == "ran":
        due.record_run(top, a["name"], out.get("now"))
        return
    if a["do"] == "run":
        code, text = sh(a["argv"], top)
        a["exit"], a["output"] = code, text[-2000:]
    if a["do"] in ("wake", "notify"):
        out[a["do"]].append(a)
    note = a.get("why", "") + (f" (exit {a['exit']})" if a.get("exit") else "")
    mtm_scan.log(main, {"kind": a["kind"], "slot": a["slot"], "what": a.get("text") or " ".join(a.get("argv", [])),
                        "note": note, "by": "tick", "duty": a["duty"]})


def stay_current(top: str, main: str, out: dict) -> None:
    """Merge the default branch into the owner slot the way /mfm does; a failure needs the model."""
    a = act("frame", "stay-current", "run", argv=MFM, text="merge-from-main in the owner slot")
    execute(a, top, main, out)
    if a["exit"]:
        try:
            status = json.loads(a["output"].splitlines()[-1]).get("status", "error")
        except (ValueError, IndexError, AttributeError):
            status = "error"
        execute(act("frame", "mfm-failed", "wake", text=f"merge-from-main in the owner slot: {status}",
                    evidence=a["output"]), top, main, out)


def summarize(main: str, top: str, out: dict) -> None:
    """The round's summary from the log: a file of its own when the round did something, latest.md always."""
    snap = mtm_scan.snapshot(top, 24)
    logged = [a for a in out["done"] if a["do"] != "ran"]
    notes = "\n".join(f"- {a['duty']} {a['kind']} {a['slot']}: {a.get('text', '')}" for a in logged) or "quiet"
    if logged or snap["findings"]:
        out["summary"] = str(mtm_scan.write_summary(main, snap, notes))
        return
    latest = mtm_scan.summary_dir(main) / "latest.md"
    latest.write_text(mtm_scan.render_summary(snap, [], [], notes))
    out["summary"] = str(latest)


def run(repo: str, dry: bool, handlers: dict, now: dt.datetime | None = None) -> dict:
    """One round. Dry: plan only, touch nothing. Returns the round as data (also what `--json` prints)."""
    out = {"dry": dry, "now": now, "wake": [], "notify": [], "done": [], "planned": []}
    problem = slot_problem(repo)
    if problem:
        out.update(stop=True, problem=problem)
        return out
    top = git(repo, "rev-parse", "--show-toplevel")
    main = mtm_scan.main_checkout(top)
    out["planned"].append(act("frame", "stay-current", "run", argv=MFM, text="merge-from-main in the owner slot"))
    if not dry:
        stay_current(top, main, out)
        out["done"].append(out["planned"][0])
    edit, go_on = role_edit(top)
    out["planned"] += edit
    rnd = plan_round(top, handlers, now) if go_on else {"due": [], "settings": {}, "actions": [], "stop": True}
    out["planned"] += rnd["actions"]
    out.update(due=rnd["due"], settings=rnd["settings"], stop=rnd["stop"])
    if not dry:
        for a in edit + rnd["actions"]:
            execute(a, top, main, out)
            out["done"].append(a)
        summarize(main, top, out)
    return out

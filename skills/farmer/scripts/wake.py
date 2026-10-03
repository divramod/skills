"""The owner's wake (plan 0007 step 6): what a tick hands to the owner's Claude session, and the waking itself.

A round's items that need the model, `wake` (judgment), `relay` (a templated message for a busy session, sent
verbatim with SendMessage), `notify` (a notice for the user, pushed batched) and the delegations that could not be
placed (`delegate-failed`), go into `~/skills/owner/<repo>/wake.json`:

  {"woken_at": <iso or null>, "items": [{"seq": n, "duty", "kind", "slot", "do", "text", "evidence"?, "brief"?,
                                         "instructions": <the file to read for this kind>}, ...]}

Items accumulate until the session handles them (`owner.py wake --done <seq>` drops every item up to `seq`). The
session is woken by typing `/owner act` into its empty prompt (deliver.py) once per batch: a tick with nothing new
adds no turn, a refused wake (the session busy, a draft) is retried by the next tick, and a wake the
session has not acted on within an hour is repeated.
"""

import datetime as dt
import json
import time
from pathlib import Path

import deliver
import mtm_scan

SKILL = Path(__file__).resolve().parents[1]
KINDS = ("wake", "relay", "notify")
SUBSKILLS = {"mtm": "merge-to-main-boss", "lead": "development-lead", "ci": "ci", "watch": "sanity-watch",
             "autoclear": "fix-autoclear"}
ACT = "/owner act"
CLEAR_AT = 10  # context percent above which a wake starts with /clear: a call re-reads the whole context
CLEARED = 60  # seconds to wait for the cleared session
REWAKE = dt.timedelta(hours=1)  # a wake the session never acted on is repeated


def wake_file(main: str) -> Path:
    return mtm_scan.state_dir(main) / "wake.json"


def instructions(duty: str, kind: str) -> str:
    """The one file the woken session reads for an item: `instructions/<duty>.<kind>.md`, else
    `instructions/<duty>.md`, else its duty's subskill, else SKILL.md."""
    for own in (SKILL / "instructions" / f"{duty}.{kind}.md", SKILL / "instructions" / f"{duty}.md",
                SKILL / "subskills" / SUBSKILLS.get(duty, "-") / "SUBSKILL.md"):
        if own.exists():
            return str(own)
    return str(SKILL / "SKILL.md")


def items(out: dict) -> list[dict]:
    """The round's items for the model: wake, relay and notify actions, and delegations that failed."""
    found = [a for k in KINDS for a in out.get(k, [])]
    found += [{"duty": "owner", "kind": "delegate-failed", "slot": d.get("slot") or "-", "do": "wake",
               "text": f"delegation failed: {d.get('title') or d.get('key')}", "evidence": d}
              for d in out.get("delegations", []) if d.get("state") == "error"]
    keep = ("duty", "kind", "slot", "do", "text", "evidence", "brief", "why", "key")
    return [{**{k: a[k] for k in keep if k in a}, "instructions": instructions(a["duty"], a["kind"])} for a in found]


def read(main: str) -> dict:
    f = wake_file(main)
    try:
        return json.loads(f.read_text()) if f.exists() else {"woken_at": None, "items": []}
    except json.JSONDecodeError:
        return {"woken_at": None, "items": []}


def write(main: str, data: dict) -> None:
    f = wake_file(main)
    if not data["items"]:
        f.unlink(missing_ok=True)
        return
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, default=str) + "\n")
    tmp.replace(f)


def owner_pane(top: str) -> str | None:
    """The pane of the agent whose checkout is the owner slot."""
    code, text = deliver.cli("list", "--json")
    try:
        data = json.loads(text) if code == 0 else []
    except json.JSONDecodeError:
        return None
    rows = data.get("list", []) if isinstance(data, dict) else data
    target = Path(top).resolve()
    return next((a.get("pane_id") for a in rows
                 if a.get("checkout") and Path(a["checkout"]).resolve() == target), None)


def small_context(pane: str, sleep=time.sleep) -> str | None:
    """Clear the owner session first when its context is large (all its state lives in files; Act records open
    threads in the log). None when it is ready for the wake, else why not."""
    a = deliver.agent(pane) or {}
    if (a.get("context_percent") or 0) < CLEAR_AT:
        return None
    why = deliver.send(pane, "/clear")
    if why:
        return f"/clear not typed: {why}"
    for _ in range(CLEARED // 2):
        sleep(2)
        b = deliver.agent(pane) or {}
        if b.get("session_id") != a.get("session_id") and b.get("state") in deliver.READY:
            return None
    return "the cleared session did not come back"


def hand_over(top: str, main: str, out: dict, now: dt.datetime) -> dict:
    """Add the round's items to wake.json and wake the owner session when it holds a batch it was not woken for.
    Returns {"items": n new, "pending": n in the file, "woken": bool, "why": refusal}."""
    data, new = read(main), items(out)
    seq = max((i["seq"] for i in data["items"]), default=0)
    for i in new:
        seq += 1
        data["items"].append({"seq": seq, **i})
    if new:
        data["woken_at"] = data.get("woken_at") if data["items"][:-len(new)] else None
    result = {"items": len(new), "pending": len(data["items"]), "woken": False}
    stale = data.get("woken_at") and now - dt.datetime.fromisoformat(data["woken_at"]) > REWAKE
    if data["items"] and (not data.get("woken_at") or stale):
        pane = owner_pane(top)
        why = (small_context(pane) or deliver.send(pane, ACT)) if pane else "no owner session"
        if why:
            result["why"] = why
        else:
            data["woken_at"], result["woken"] = now.isoformat(timespec="seconds"), True
            mtm_scan.log(main, {"kind": "wake", "slot": "owner", "what": f"{ACT}: {len(data['items'])} items",
                                "note": "", "by": "tick", "do": "wake"})
    write(main, data)
    return result


def done(main: str, upto: int) -> int:
    """Drop the items the woken session handled (seq ≤ upto); a later batch is woken for by the next tick.
    Returns the items left."""
    data = read(main)
    data["items"] = [i for i in data["items"] if i["seq"] > upto]
    data["woken_at"] = None
    write(main, data)
    return len(data["items"])

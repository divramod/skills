"""What each record of a plan folder must hold beyond its keys and sections: rules 3, 4 and 6 of hal2's decision
record `record-formats` (ported from the validator of hal2 plan 0202)."""

import re

import envelope
from records import Record, Tree

D_HEAD = re.compile(r"^D(\d+) · (\d{4}-\d{2}-\d{2}) · (user|farmer|lead|agent) · "
                    r"(in-force|promoted|superseded|ended \d{4}-\d{2}-\d{2})$")
Q_HEAD = re.compile(r"^Q(\d+) · (\d{4}-\d{2}-\d{2}) · (agent|user) · "
                    r"(open|answered \d{4}-\d{2}-\d{2}|dropped \d{4}-\d{2}-\d{2})$")
MACHINE_LOCAL = {"an absolute home path": r"(/Users/|/home/)\w", "a PID": r"\b(PID|pid)\b",
                 "a pane id": r"(^|\s)%\d+\b", "a session id": r"\bsession_[0-9A-Za-z]{6,}"}


def folder(rec: Record) -> str:
    return rec.rel.rsplit("/", 1)[0]


def number(rec: Record) -> int:
    m = re.search(r"(\d{4})-[^/]+/[^/]+$", rec.rel)
    return int(m.group(1)) if m else -1


def ledger(rec: Record, head: re.Pattern, letter: str) -> tuple[dict, list[str]]:
    """A ledger's entries by number ({n: (state, text)}) and the problems of their headings."""
    found, problems = {}, []
    for title, text in envelope.entries(rec.body):
        m = head.match(title.strip())
        if not m:
            problems.append(f"entry heading does not match the {letter}<n> form: {title.strip()}")
        elif int(m.group(1)) in found:
            problems.append(f"{letter}{m.group(1)}: the number is used twice")
        else:
            found[int(m.group(1))] = (m.group(3), m.group(4).split()[0], text)
    if sorted(found) != list(range(1, len(found) + 1)):
        problems.append(f"{letter} numbers are not 1..{len(found)} without gaps")
    return found, problems


def with_plan(rec: Record, tree: Tree) -> list[str]:
    """A plan-folder record names its plan, and is closed exactly when that plan is no longer open."""
    problems = []
    if rec.meta.get("plan") != number(rec):
        problems.append(f"`plan: {rec.meta.get('plan')}` is not the folder's number {number(rec)}")
    plan = tree.record(folder(rec) + "/plan.md")
    if plan and plan.type == "Plan" and (plan.meta.get("status") == "open") != (rec.meta.get("status") == "open"):
        problems.append(f"status `{rec.meta.get('status')}` but the plan is `{plan.meta.get('status')}`")
    return problems


def plan(rec: Record, tree: Tree) -> list[str]:
    problems = []
    if rec.meta.get("id") != number(rec):
        problems.append(f"`id: {rec.meta.get('id')}` is not the folder's number {number(rec)}")
    rows = [[c.strip() for c in line.strip().strip("|").split("|")]
            for line in envelope.section(rec.body, "Steps").split("\n") if re.match(r"^\|\s*\d+\s*\|", line)]
    ids = [r[0] for r in rows]
    if not rows:
        problems.append("the Steps table has no step")
    if len(ids) != len(set(ids)):
        problems.append("a step number is used twice")
    all_done = bool(rows) and all(r[-1].startswith("done") for r in rows)
    if (rec.meta.get("status") == "done") != all_done:
        problems.append(f"status `{rec.meta.get('status')}` does not fit the step table (all done: {all_done})")
    if (rec.meta.get("status") == "done") != bool(rec.meta.get("finished")):
        problems.append("`finished` is set exactly when the status is `done`")
    return problems


def decisions(rec: Record, tree: Tree) -> list[str]:
    found, problems = ledger(rec, D_HEAD, "D")
    problems += with_plan(rec, tree)
    questions = tree.record(folder(rec) + "/questions.md")
    asked = ledger(questions, Q_HEAD, "Q")[0] if questions else {}
    for n, (who, state, text) in found.items():
        get = lambda name: envelope.field(text, name)  # noqa: E731
        if not get("D"):
            problems.append(f"D{n}: no **D:** line")
        if who != "agent" and not get("Words"):
            problems.append(f"D{n}: decided by `{who}`, but no **Words:** line with the quoted words")
        if (state == "promoted") != bool(get("Record")):
            problems.append(f"D{n}: a **Record:** line exactly when the entry is `promoted`")
        if (state == "superseded") != bool(get("By")):
            problems.append(f"D{n}: a **By:** line exactly when the entry is `superseded`")
        by = re.fullmatch(r"D(\d+)", get("By"))
        if get("By") and (not by or int(by.group(1)) not in found or int(by.group(1)) == n):
            problems.append(f"D{n}: **By:** names no other entry: {get('By')}")
        q = re.fullmatch(r"Q(\d+)", get("From"))
        if get("From") and (not q or envelope.field(asked.get(int(q.group(1)), ("", "", ""))[2], "Decision") != f"D{n}"):
            problems.append(f"D{n}: **From:** {get('From')}, but that question does not link back with **Decision:** D{n}")
        if get("Record"):
            problems += promoted(rec, tree, n, text)
    return problems


def promoted(rec: Record, tree: Tree, n: int, text: str) -> list[str]:
    """A promoted entry links a decision record whose `origin` names the entry's plan."""
    targets = [tree.resolve(rec.rel, t) for t in envelope.links(envelope.field(text, "Record"))]
    record = tree.record(targets[0]) if len(targets) == 1 and targets[0] else None
    if not record or record.type != "Decision Record":
        return [f"D{n}: **Record:** links no decision record"]
    if folder(rec) + "/plan.md" not in (record.meta.get("origin") or []):
        return [f"D{n}: {targets[0]} does not name this plan in its `origin`"]
    return []


def questions(rec: Record, tree: Tree) -> list[str]:
    found, problems = ledger(rec, Q_HEAD, "Q")
    problems += with_plan(rec, tree)
    ledger_d = tree.record(folder(rec) + "/decisions.md")
    decided = ledger(ledger_d, D_HEAD, "D")[0] if ledger_d else {}
    for n, (_, state, text) in found.items():
        answer = envelope.field(text, "A")
        if not envelope.field(text, "Q"):
            problems.append(f"Q{n}: no **Q:** line")
        if (state == "open") == bool(answer):
            problems.append(f"Q{n}: `{state}` does not fit its **A:** line (an open entry has none, the others one)")
        if state == "open" and rec.meta.get("status") == "closed":
            problems.append(f"Q{n}: open, but the ledger is `closed`")
        d = re.fullmatch(r"D(\d+)", envelope.field(text, "Decision"))
        back = envelope.field(decided.get(int(d.group(1)), ("", "", ""))[2], "From") if d else ""
        if envelope.field(text, "Decision") and back != f"Q{n}":
            problems.append(f"Q{n}: **Decision:** {envelope.field(text, 'Decision')}, but that decision does not link "
                            f"back with **From:** Q{n}")
    return problems


def handoff(rec: Record, tree: Tree) -> list[str]:
    problems = with_plan(rec, tree)
    if "Done when:" not in envelope.section(rec.body, "Next"):
        problems.append("`## Next` has no `Done when:` line")
    if not re.search(r"^> \S", envelope.section(rec.body, "Start with"), re.M):
        problems.append("`## Start with` has no quoted prompt")
    for what, pattern in MACHINE_LOCAL.items():
        if re.search(pattern, rec.body, re.M):
            problems.append(f"holds a machine-local fact ({what})")
    return problems


BY_TYPE = {"Plan": plan, "Decisions": decisions, "Questions": questions, "Handoff": handoff}

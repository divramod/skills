#!/usr/bin/env python3
"""The decisions this checkout holds, and the farmer's decision check (skills plans 0008, 0012).

  decisions.py [--farmer-repo <repo>] [--json]
  decisions.py --check

Lists the decisions a session continuing with `/handoff c` has: HANDOFF.md's Decisions (the index of every user
decision in force), then the current plan's Decisions and Pre-authorized (the plan `plans/CURRENT_PLAN` names, else
the one HANDOFF.md links; an item holding one of the index's quotes is left out) and HANDOFF.md's Open. Prints the farmer
HANDOFF.md names (`Farmer: <session> (<repo>)`, written by /handoff for a servant), the slot id the farmer knows
(`<slot>`, or `<repo>/<slot>` when the farmer belongs to another repository) and the message to send it:

  decision check <slot>: I have these decisions: (1) ... (2) .... Did I forget one?

In a parallel plan's subservant slot (skills plan 0013: `plans/LEAD` holds `<lead-slot> <plan> <step>`) it adds
`lead` ({slot, plan, step}) to the JSON and a `lead:` line to the text: `/handoff c` there continues that one step
only, never the plan and never a landing.

`--check` validates HANDOFF.md's Decisions section after /handoff wrote it: the section exists (`- none` when the
work holds no user decision) and every line is `- <YYYY-MM-DD> "<the user's words>" (<who relayed it>) · home: <plan |
INTENT.md | .adr/<file>.md | a relative path>[ · ended <YYYY-MM-DD>: <why>]`, its home file exists and holds the
quote (when the quote is distinctive). It prints `ok` or one problem per line.

Exit 0 printed (or `--check` ok), 1 `--check` found problems, 2 git missing.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ITEM_CHARS = 240
FARMER = re.compile(r"^Farmer:\s*`?([^\s`(]+)`?(?:\s*\(([^)]+)\))?", re.M)
PLAN_LINK = re.compile(r"\]\(((?:\./)?plans/[^)\s]+/plan\.md)\)")
QUOTED = re.compile(r'"([^"]+)"|“([^”]+)”')
DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})\b")
HOME = re.compile(r"\bhome:\s*(.+?)\s*(?:·\s*ended\b.*)?$", re.I)
ENDED = re.compile(r"·\s*ended\b(.*)$", re.I)
MD_PATH = re.compile(r"\(([^)\s]+\.md)\)|(?<![\w/])((?:\.?[\w-]+/)*[\w.-]+\.md)\b")
STOP = {"with", "that", "this", "from", "into", "have", "after", "before", "when", "then", "than", "them", "they",
        "their", "there", "what", "which", "where", "every", "each", "also", "only", "should", "would", "could", "must",
        "will", "were", "been", "being", "does", "done", "make", "made", "user", "slot", "plan", "step", "steps",
        "decided", "decision", "decisions", "farmer", "servant", "skill"}
RUN = 8  # a long quote is found by 8 consecutive words holding 2 key words


def git(*args: str, cwd: str | None = None) -> str:
    return subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True).stdout.strip()


def section(text: str, title: str) -> list[str]:
    """The bullets of a `## <title>` section, each joined into one line; placeholders (`- <...>`) left out."""
    m = re.search(rf"^## {re.escape(title)}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    items: list[str] = []
    for line in (m.group(1) if m else "").splitlines():
        if re.match(r"^\s{0,1}[-*] ", line):
            items.append(line.strip()[2:].strip())
        elif items and line.startswith("  ") and line.strip():
            items[-1] += " " + line.strip()
    return [i for i in items if i and not i.startswith("<")]


def flat(text: str) -> list[str]:
    """Lower-case alphanumeric words: case, whitespace and punctuation do not matter."""
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def key_words(ws: list[str]) -> set[str]:
    return {w for w in ws if len(w) >= 4 and w not in STOP}


def found(quote: str, text: str) -> bool | None:
    """Does `text` hold the user's quote? A quote of 4-8 words with a key word occurs whole; a longer one by a run of 8
    consecutive words holding 2 key words. None when the quote is too short to tell (fewer than 4 words, no key word)."""
    q, hay = flat(quote), f" {' '.join(flat(text))} "
    if len(q) < 4 or not key_words(q):
        return None
    if len(q) <= RUN:
        return f" {' '.join(q)} " in hay
    runs = (q[i:i + RUN] for i in range(len(q) - RUN + 1))
    return any(len(key_words(r)) >= 2 and f" {' '.join(r)} " in hay for r in runs)


def quoted(item: str) -> list[str]:
    return [(a or b).strip() for a, b in QUOTED.findall(item)]


def home_file(root: Path, home: str, plan: Path | None) -> Path | None:
    """The file a Decisions line's `home:` names: `plan` is the current plan, else the first `.md` path in it."""
    if re.match(r"plan\b(?!s/)", home, re.I):
        return plan
    m = MD_PATH.search(home)
    return root / (m.group(1) or m.group(2)) if m else None


def check(root: Path) -> list[str]:
    """The problems of HANDOFF.md's Decisions section; empty when it is complete."""
    path = root / "HANDOFF.md"
    if not path.exists():
        return ["no HANDOFF.md"]
    handoff = path.read_text()
    if not re.search(r"^## Decisions\s*$", handoff, re.M):
        return ["HANDOFF.md has no `## Decisions` section (write `- none` when the work holds no user decision)"]
    items = section(handoff, "Decisions")
    if not items:
        return ["`## Decisions` is empty: list every user decision in force, or `- none`"]
    plan, problems = plan_file(root, handoff), []
    for n, item in enumerate(items, 1):
        if re.fullmatch(r"none\.?", item, re.I):
            continue
        say = lambda why: problems.append(f"Decisions line {n}: {why}: {short(item)}")  # noqa: E731
        if not DATE.match(item):
            say("starts with no date (YYYY-MM-DD)")
        quotes = quoted(item.split("home:")[0])
        if not quotes:
            say('quotes no user\'s words ("...")')
        ended = ENDED.search(item)
        if ended and not re.match(r"\s*\d{4}-\d{2}-\d{2}", ended.group(1)):
            say("`ended` without a date")
        m = HOME.search(item)
        if not m:
            say("names no home (`· home: plan | INTENT.md | <path>.md`)")
            continue
        f = home_file(root, m.group(1), plan)
        if f is None or not f.exists():
            say(f"its home {m.group(1)!r} is no existing file" + (" (no current plan)" if f is None else ""))
        elif quotes and all(found(q, f.read_text()) is False for q in quotes):
            say(f"its home {f.relative_to(root)} does not hold the quote (record it there with the user's words)")
    return problems


def plan_file(root: Path, handoff: str) -> Path | None:
    cur = root / "plans" / "CURRENT_PLAN"
    slug = cur.read_text().strip() if cur.exists() else ""
    if slug and (root / "plans" / slug / "plan.md").exists():
        return root / "plans" / slug / "plan.md"
    m = PLAN_LINK.search(handoff)
    return root / m.group(1) if m and (root / m.group(1)).exists() else None


def lead_of(root: Path) -> dict | None:
    """The subservant marker plans/LEAD: {slot, plan, step}; None without one (or a broken one)."""
    f = root / "plans" / "LEAD"
    parts = f.read_text().split() if f.is_file() else []
    return {"slot": parts[0], "plan": parts[1], "step": parts[2]} if len(parts) >= 3 else None


def short(item: str) -> str:
    return item if len(item) <= ITEM_CHARS else item[:ITEM_CHARS - 1].rstrip() + "…"


def collect(root: Path, main_name: str, farmer_repo: str | None) -> dict:
    handoff_path = root / "HANDOFF.md"
    handoff = handoff_path.read_text() if handoff_path.exists() else ""
    plan = plan_file(root, handoff)
    plan_text = plan.read_text() if plan else ""
    index = [d for d in section(handoff, "Decisions") if not re.fullmatch(r"none\.?", d, re.I)]
    said = [q for d in index for q in quoted(d.split("home:")[0])]
    indexed = lambda d: any(found(q, d) for q in said)  # noqa: E731
    have = [("HANDOFF.md Decisions", d) for d in index]
    have += [("plan Decisions", d) for d in section(plan_text, "Decisions") if not indexed(d)]
    have += [("plan Pre-authorized", d) for d in section(plan_text, "Pre-authorized") if not indexed(d)]
    have += [("HANDOFF.md Open", d) for d in section(handoff, "Open")]
    m = FARMER.search(handoff)
    farmer, repo = (m.group(1), (m.group(2) or "").strip()) if m else (None, "")
    repo = farmer_repo or repo or main_name
    slot = root.name if repo == main_name else f"{main_name}/{root.name}"
    listed = " ".join(f"({n}) {short(d)}" for n, (_, d) in enumerate(have, 1)).rstrip(".") or "none"
    return {"root": str(root), "plan": str(plan.relative_to(root)) if plan else None, "lead": lead_of(root),
            "farmer": farmer,
            "farmer_repo": repo, "slot": slot, "decisions": [{"from": s, "text": d} for s, d in have],
            "message": f"decision check {slot}: I have these decisions: {listed}. Did I forget one?"}


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--farmer-repo", help="the repository the farmer serves (default: HANDOFF.md's Farmer line, "
                                         "else this one)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--check", action="store_true", help="validate HANDOFF.md's Decisions section")
    args = p.parse_args(argv)
    if not shutil.which("git"):
        print("decisions.py: git is missing; run install-prerequisites.sh", file=sys.stderr)
        return 2
    root = Path(git("rev-parse", "--show-toplevel") or ".").resolve()
    common = git("rev-parse", "--path-format=absolute", "--git-common-dir")
    main_name = Path(common).parent.name if common else root.name
    if args.check:
        problems = check(root)
        print("\n".join(problems) or "ok")
        return 1 if problems else 0
    r = collect(root, main_name, args.farmer_repo)
    if args.json:
        print(json.dumps(r, indent=1))
        return 0
    print(f"plan: {r['plan'] or 'none'}")
    if r["lead"]:
        lead = r["lead"]
        print(f"lead: slot {lead['slot']}, plan {lead['plan']}, step {lead['step']}: a subservant, continue that one "
              "step only (never the plan, never a landing)")
    for n, d in enumerate(r["decisions"], 1):
        print(f"{n:3}. [{d['from']}] {short(d['text'])}")
    print(f"farmer: {r['farmer'] or 'none named in HANDOFF.md: ListAgents, the session in the farmer slot of ' + r['farmer_repo']}"
          f" (repo {r['farmer_repo']}, slot id {r['slot']})")
    print(f"message: {r['message']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

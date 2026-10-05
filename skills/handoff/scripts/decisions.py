#!/usr/bin/env python3
"""The decisions this checkout holds, and the farmer's decision check (skills plan 0008).

  decisions.py [--farmer-repo <repo>] [--json]

Lists the decisions a session continuing with `/handoff c` has: the current plan's Decisions and Pre-authorized
(the plan `plans/CURRENT_PLAN` names, else the one HANDOFF.md links) and HANDOFF.md's Open. Prints the farmer
HANDOFF.md names (`Farmer: <session> (<repo>)`, written by /handoff for a servant), the slot id the farmer knows
(`<slot>`, or `<repo>/<slot>` when the farmer belongs to another repository) and the message to send it:

  decision check <slot>: I have these decisions: (1) ... (2) .... Did I forget one?

Exit 0 printed, 2 git missing.
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


def plan_file(root: Path, handoff: str) -> Path | None:
    cur = root / "plans" / "CURRENT_PLAN"
    slug = cur.read_text().strip() if cur.exists() else ""
    if slug and (root / "plans" / slug / "plan.md").exists():
        return root / "plans" / slug / "plan.md"
    m = PLAN_LINK.search(handoff)
    return root / m.group(1) if m and (root / m.group(1)).exists() else None


def short(item: str) -> str:
    return item if len(item) <= ITEM_CHARS else item[:ITEM_CHARS - 1].rstrip() + "…"


def collect(root: Path, main_name: str, farmer_repo: str | None) -> dict:
    handoff_path = root / "HANDOFF.md"
    handoff = handoff_path.read_text() if handoff_path.exists() else ""
    plan = plan_file(root, handoff)
    plan_text = plan.read_text() if plan else ""
    found = [("plan Decisions", d) for d in section(plan_text, "Decisions")]
    found += [("plan Pre-authorized", d) for d in section(plan_text, "Pre-authorized")]
    found += [("HANDOFF.md Open", d) for d in section(handoff, "Open")]
    m = FARMER.search(handoff)
    farmer, repo = (m.group(1), (m.group(2) or "").strip()) if m else (None, "")
    repo = farmer_repo or repo or main_name
    slot = root.name if repo == main_name else f"{main_name}/{root.name}"
    listed = " ".join(f"({n}) {short(d)}" for n, (_, d) in enumerate(found, 1)).rstrip(".") or "none"
    return {"root": str(root), "plan": str(plan.relative_to(root)) if plan else None, "farmer": farmer,
            "farmer_repo": repo, "slot": slot, "decisions": [{"from": s, "text": d} for s, d in found],
            "message": f"decision check {slot}: I have these decisions: {listed}. Did I forget one?"}


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--farmer-repo", help="the repository the farmer serves (default: HANDOFF.md's Farmer line, "
                                         "else this one)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    if not shutil.which("git"):
        print("decisions.py: git is missing; run install-prerequisites.sh", file=sys.stderr)
        return 2
    root = Path(git("rev-parse", "--show-toplevel") or ".").resolve()
    common = git("rev-parse", "--path-format=absolute", "--git-common-dir")
    main_name = Path(common).parent.name if common else root.name
    r = collect(root, main_name, args.farmer_repo)
    if args.json:
        print(json.dumps(r, indent=1))
        return 0
    print(f"plan: {r['plan'] or 'none'}")
    for n, d in enumerate(r["decisions"], 1):
        print(f"{n:3}. [{d['from']}] {short(d['text'])}")
    print(f"farmer: {r['farmer'] or 'none named in HANDOFF.md: ListAgents, the session in the farmer slot of ' + r['farmer_repo']}"
          f" (repo {r['farmer_repo']}, slot id {r['slot']})")
    print(f"message: {r['message']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

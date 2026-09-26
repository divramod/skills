#!/usr/bin/env python3
"""Deterministic bookkeeping for plans under plans/ at the repository root.

A plan is a folder plans/<NNNN>-<slug>/ holding plan.md and the plan's helper files; plan.md has a markdown table whose header has the columns `#`, `Step` and `Status`
(optionally `Done when`). plans/CURRENT_PLAN holds the slug of the active plan (the Claude statusline shows it).
A flat plans/<NNNN>-<slug>.md from before the folder layout is still read and updated.

  plan.py new "<title>" [--goal "<goal>"] [--no-current] [--fetch]
                                                           create the next plan from the template; its number
                                                           is unique across all worktrees and branches
                                                           (plan_number.py; --fetch sees other clones too)
  plan.py current                                          print the current plan as JSON
  plan.py list                                             print every plan as JSON
  plan.py use <slug-or-number>                             make a plan current
  plan.py status <step> "<status>" [--plan <slug>]         set one step's Status cell
  plan.py grilled [--plan <slug>]                          set the plan's `Grilled:` line to today
  plan.py check                                            exit 1 when a plan number is used twice

Run from anywhere inside the repo, or pass --root. Prints JSON on stdout; exits 1 with a message on stderr.
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import plan_number

PLANS = Path("plans")
POINTER = "CURRENT_PLAN"
PLAN_RE = re.compile(r"^(\d{4})-[a-z0-9-]+$")
MAIN = "plan.md"
TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "plan.md"


class PlanError(Exception):
    pass


def find_root(start: Path) -> Path:
    for folder in [start, *start.parents]:
        if (folder / ".git").exists():
            return folder
    raise PlanError(f"not inside a git repository: {start}")


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if not slug:
        raise PlanError("title needs at least one letter or digit")
    return slug[:60].rstrip("-")


def slug_of(path: Path) -> str:
    """`0002-foo` for plans/0002-foo/plan.md (and for a flat plans/0002-foo.md)."""
    return path.parent.name if path.name == MAIN else path.stem


def plan_files(root: Path) -> list[Path]:
    """Every plan's markdown file: plans/<slug>/plan.md, or a flat plans/<slug>.md."""
    folder = root / PLANS
    if not folder.is_dir():
        return []
    found = [p / MAIN for p in folder.iterdir() if p.is_dir() and PLAN_RE.match(p.name) and (p / MAIN).is_file()]
    found += [p for p in folder.iterdir() if p.is_file() and p.suffix == ".md" and PLAN_RE.match(p.stem)]
    return sorted(found, key=slug_of)


def resolve(root: Path, ref: str) -> Path:
    """A plan by slug (`0002-foo`), file name, or bare number (`2`, `0002`)."""
    ref = ref.strip().removesuffix(".md").removesuffix("/" + MAIN).rstrip("/")
    for path in plan_files(root):
        slug = slug_of(path)
        if slug == ref or (ref.isdigit() and int(ref) == int(slug[:4])):
            return path
    raise PlanError(f"no plan matches '{ref}' in {PLANS}")


def current_path(root: Path) -> Path:
    pointer = root / PLANS / POINTER
    if not pointer.is_file() or not pointer.read_text().strip():
        raise PlanError(f"no current plan: {PLANS / POINTER} is missing or empty")
    return resolve(root, pointer.read_text().strip())


def set_current(root: Path, path: Path) -> None:
    (root / PLANS / POINTER).write_text(slug_of(path) + "\n")


def split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def steps_table(lines: list[str]) -> tuple[int, dict[str, int]]:
    """Index of the step table's header line and its column positions."""
    for i, line in enumerate(lines):
        if line.lstrip().startswith("|"):
            cells = [c.lower() for c in split_row(line)]
            if "#" in cells and "step" in cells and "status" in cells:
                return i, {name: cells.index(name) for name in cells}
    raise PlanError("no step table with columns '#', 'Step' and 'Status'")


def read_steps(text: str) -> list[dict]:
    lines = text.splitlines()
    try:
        header, cols = steps_table(lines)
    except PlanError:
        return []
    steps = []
    for line in lines[header + 2:]:
        if not line.lstrip().startswith("|"):
            break
        cells = split_row(line)
        steps.append({
            "number": cells[cols["#"]],
            "step": cells[cols["step"]],
            "done_when": cells[cols["done when"]] if "done when" in cols else "",
            "status": cells[cols["status"]],
        })
    return steps


def describe(root: Path, path: Path) -> dict:
    text = path.read_text()
    steps = read_steps(text)
    title = next((l[2:].strip() for l in text.splitlines() if l.startswith("# ")), slug_of(path))
    grilled = next((l.split(":", 1)[1].strip() for l in text.splitlines() if l.startswith("Grilled:")), "")
    open_steps = [s for s in steps if not s["status"].lower().startswith("done")]
    pointer = root / PLANS / POINTER
    return {
        "slug": slug_of(path),
        "path": str(path.relative_to(root)),
        "title": title,
        "current": pointer.is_file() and pointer.read_text().strip() == slug_of(path),
        "grilled": grilled,
        "done": len(steps) - len(open_steps),
        "total": len(steps),
        "next": open_steps[0] if open_steps else None,
        "steps": steps,
    }


def new_plan(root: Path, title: str, goal: str, make_current: bool, fetch: bool = False) -> Path:
    slug = slugify(title)
    if fetch:
        plan_number.git(root, "fetch", "--all", "--quiet")
    try:
        number = plan_number.next_number(root, slug)
    except plan_number.NumberError as error:
        raise PlanError(str(error)) from error
    path = root / PLANS / f"{number:04d}-{slug}" / MAIN
    path.parent.mkdir(parents=True, exist_ok=True)
    text = TEMPLATE.read_text().format(
        number=f"{number:04d}", title=title, goal=goal or "<one or two sentences>",
        date=dt.date.today().isoformat(),
    )
    path.write_text(text)
    if make_current:
        set_current(root, path)
    return path


def set_status(path: Path, step: str, status: str) -> None:
    lines = path.read_text().splitlines(keepends=True)
    header, cols = steps_table([l.rstrip("\n") for l in lines])
    for i in range(header + 2, len(lines)):
        if not lines[i].lstrip().startswith("|"):
            break
        cells = split_row(lines[i])
        if cells[cols["#"]] == step:
            cells[cols["status"]] = status
            lines[i] = "| " + " | ".join(cells) + " |\n"
            path.write_text("".join(lines))
            return
    raise PlanError(f"no step '{step}' in {slug_of(path)}")


def set_grilled(path: Path) -> None:
    today = dt.date.today().isoformat()
    lines = path.read_text().splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("Grilled:"):
            lines[i] = f"Grilled: {today}\n"
            break
    else:
        title = next((i for i, l in enumerate(lines) if l.startswith("# ")), -1)
        lines.insert(title + 1, f"\nGrilled: {today}\n")
    path.write_text("".join(lines))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, help="repository root (default: found from the current directory)")
    sub = parser.add_subparsers(dest="command", required=True)
    p_new = sub.add_parser("new")
    p_new.add_argument("title")
    p_new.add_argument("--goal", default="")
    p_new.add_argument("--no-current", action="store_true")
    p_new.add_argument("--fetch", action="store_true")
    sub.add_parser("current")
    sub.add_parser("list")
    p_use = sub.add_parser("use")
    p_use.add_argument("plan")
    p_status = sub.add_parser("status")
    p_status.add_argument("step")
    p_status.add_argument("status")
    p_status.add_argument("--plan")
    p_grilled = sub.add_parser("grilled")
    p_grilled.add_argument("--plan")
    sub.add_parser("check")
    args = parser.parse_args(argv)

    try:
        root = args.root.resolve() if args.root else find_root(Path.cwd())
        if args.command == "check":
            return plan_number.main(["--root", str(root), "check"])
        if args.command == "new":
            result = describe(root, new_plan(root, args.title, args.goal, not args.no_current, args.fetch))
        elif args.command == "current":
            result = describe(root, current_path(root))
        elif args.command == "list":
            result = [describe(root, p) for p in plan_files(root)]
        elif args.command == "use":
            path = resolve(root, args.plan)
            set_current(root, path)
            result = describe(root, path)
        else:
            path = resolve(root, args.plan) if args.plan else current_path(root)
            if args.command == "status":
                set_status(path, args.step, args.status)
            else:
                set_grilled(path)
            result = describe(root, path)
    except PlanError as error:
        print(f"plan.py: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

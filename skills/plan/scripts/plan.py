#!/usr/bin/env python3
"""Deterministic bookkeeping for plans under plans/ at the repository root.

A plan is a folder plans/<NNNN>-<slug>/ holding plan.md and the plan's helper files; plan.md has a markdown table whose header has the columns `#`, `Step` and `Status`
(optionally `Done when`). plans/CURRENT_PLAN holds the slug of the active plan (the Claude statusline shows it).
A flat plans/<NNNN>-<slug>.md from before the folder layout is still read and updated.

  plan.py new "<title>" [--goal "<goal>"] [--research] [--no-current] [--fetch]
                                                           create the next plan from the template; its number
                                                           is unique across all worktrees and branches
                                                           (plan_number.py; --fetch sees other clones too);
                                                           --research: a research plan, slug <NNNN>-research-<topic>;
                                                           writes `Landing: auto` (--manual-landing: manual)
  plan.py current                                          print the current plan as JSON
  plan.py list                                             print every plan as JSON
  plan.py use <slug-or-number>                             make a plan current
  plan.py status <step> "<status>" [--plan <slug>]         set one step's Status cell
  plan.py grilled [--plan <slug>]                          set the plan's `Grilled:` line to today
  plan.py landing auto|manual [--plan <slug>]              set the plan's `Landing:` line: auto lands the plan
                                                           with /mtm when its last step is done, manual waits
                                                           for the user's /mtm (a plan without the line)
  plan.py check                                            exit 1 when a plan number is used twice
  plan.py -g ...                                           the same on the global plans folder (hal2's
                                                           plans.toml root, default ~/Documents/hal2/plans;
                                                           --global-root <dir> overrides): new (through
                                                           `hal2-cli-plans new --global`), list, status,
                                                           grilled with --plan <n>; no CURRENT_PLAN there

Run from anywhere inside the repo, or pass --root. Prints JSON on stdout; exits 1 with a message on stderr.

The JSON's `landing` is the plan's `Landing:` line (auto|manual; none for a global plan), each step's
`after_landing` says its done-when starts with "after the landing" (or the older "after the user's `/mtm`"), `next`
is the first open step to run before the landing (an after-landing step only when no other is open), `land` is
`ready` when no open step must run before the landing (`wait` otherwise; `manual`, `none` from `landing`), and
`problems` lists after-landing steps followed by steps that are not.
"""
import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import plan_number

PLANS = Path("plans")
POINTER = "CURRENT_PLAN"
PLAN_RE = re.compile(r"^(\d{4})-[a-z0-9-]+$")
MAIN = "plan.md"
TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "plan.md"
RESEARCH = "research"
LANDINGS = ("auto", "manual")
AFTER_LANDING = ("after the landing", "after the user's `/mtm`", "after the user's /mtm")
GLOBAL = False


class PlanError(Exception):
    pass


def use_global(folder: Path) -> Path:
    """Work on the global plans folder `folder`: plans are `folder/<slug>/plan.md`; the root to pass on."""
    global PLANS, GLOBAL
    PLANS = Path(folder.name)
    GLOBAL = True
    return folder.parent


def global_folder() -> Path:
    """hal2's global plans folder (`hal2-cli-plans settings --json`)."""
    if shutil.which("hal2-cli-plans") is None:
        raise PlanError("hal2-cli-plans is missing: install hal2 (cargo install --path apps/hal2-cli-plans)")
    out = subprocess.run(["hal2-cli-plans", "settings", "--json"], capture_output=True, text=True)
    if out.returncode != 0:
        raise PlanError(f"hal2-cli-plans settings: {out.stderr.strip()}")
    return Path(json.loads(out.stdout)["root"])


def new_global_plan(folder: Path, title: str, goal: str, research: bool) -> Path:
    """A global plan, numbered and written by hal2 (`hal2-cli-plans new --global`)."""
    if shutil.which("hal2-cli-plans") is None:
        raise PlanError("hal2-cli-plans is missing: install hal2 (cargo install --path apps/hal2-cli-plans)")
    args = ["hal2-cli-plans", "new", title, "--global", "--json"]
    if goal:
        args += ["--goal", goal]
    if research:
        args.append("--research")
    out = subprocess.run(args, capture_output=True, text=True)
    if out.returncode != 0:
        raise PlanError(f"hal2-cli-plans new: {out.stderr.strip()}")
    path = Path(json.loads(out.stdout)["path"]).resolve()
    if path.parent.parent.resolve() != folder.resolve():
        raise PlanError(f"hal2-cli-plans created {path}, outside the global folder {folder}")
    return path


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


def research_slug(slug: str) -> str:
    """`research-<slug>` for a research plan, unless the slug already starts with it."""
    if slug == RESEARCH or slug.startswith(RESEARCH + "-"):
        return slug
    return f"{RESEARCH}-{slug}"[:60].rstrip("-")


def is_research(slug: str) -> bool:
    """A research plan: `<NNNN>-research-<topic>`."""
    name = slug[5:]
    return name == RESEARCH or name.startswith(RESEARCH + "-")


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
    ref = pointer.read_text().strip()
    try:
        return resolve(root, ref)
    except PlanError:
        # A shot (`<shotfile>/<n>`) or a task name: current work, but no plan.
        raise PlanError(f"no current plan: {PLANS / POINTER} names '{ref}', which is not a plan") from None


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
    for step in steps:
        step["after_landing"] = step["done_when"].lower().lstrip("*_ ").startswith(AFTER_LANDING)
    return steps


def header_value(text: str, key: str) -> str:
    """The value of a `<key>: <value>` line above the plan's first section."""
    for line in text.splitlines():
        if line.startswith("## "):
            break
        if line.startswith(key + ":"):
            return line.split(":", 1)[1].strip()
    return ""


def landing_of(text: str) -> str:
    """auto, manual (also for a plan without the line or with an unknown value) or none (a global plan)."""
    if GLOBAL:
        return "none"
    value = header_value(text, "Landing").lower()
    return value if value in LANDINGS else "manual"


def problems_of(steps: list[dict]) -> list[str]:
    """After-landing steps that other steps follow: they belong at the end of the table."""
    problems = []
    for i, step in enumerate(steps):
        later = [s["number"] for s in steps[i + 1:] if not s["after_landing"]]
        if step["after_landing"] and later:
            problems.append(f"step {step['number']} is checked after the landing but step(s) {', '.join(later)} "
                            "follow it: move it to the end, a plan lands once, after all its other steps")
    return problems


def describe(root: Path, path: Path) -> dict:
    text = path.read_text()
    steps = read_steps(text)
    title = next((l[2:].strip() for l in text.splitlines() if l.startswith("# ")), slug_of(path))
    grilled = header_value(text, "Grilled")
    open_steps = [s for s in steps if not s["status"].lower().startswith("done")]
    before_landing = [s for s in open_steps if not s["after_landing"]]
    landing = landing_of(text)
    land = landing if landing != "auto" else ("wait" if before_landing else "ready")
    pointer = root / PLANS / POINTER
    return {
        "slug": slug_of(path),
        "path": str(path.relative_to(root)),
        "title": title,
        "research": is_research(slug_of(path)),
        "current": pointer.is_file() and pointer.read_text().strip() == slug_of(path),
        "grilled": grilled,
        "done": len(steps) - len(open_steps),
        "total": len(steps),
        "next": (before_landing or open_steps or [None])[0],
        "landing": landing,
        "land": land,
        "problems": problems_of(steps),
        "steps": steps,
    }


def new_plan(root: Path, title: str, goal: str, make_current: bool, fetch: bool = False,
             research: bool = False, landing: str = "auto") -> Path:
    slug = research_slug(slugify(title)) if research else slugify(title)
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
        date=dt.date.today().isoformat(), landing=landing,
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


def set_header(path: Path, key: str, value: str) -> None:
    """Set the plan's `<key>: <value>` line, inserting it below the title when missing."""
    lines = path.read_text().splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("## "):
            break
        if line.startswith(key + ":"):
            lines[i] = f"{key}: {value}\n"
            path.write_text("".join(lines))
            return
    title = next((i for i, l in enumerate(lines) if l.startswith("# ")), -1)
    lines.insert(title + 1, f"\n{key}: {value}\n")
    path.write_text("".join(lines))


def set_grilled(path: Path) -> None:
    set_header(path, "Grilled", dt.date.today().isoformat())


def set_landing(path: Path, landing: str) -> None:
    if GLOBAL:
        raise PlanError("a global plan never lands: it belongs to no repository")
    set_header(path, "Landing", landing)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, help="repository root (default: found from the current directory)")
    parser.add_argument("-g", "--global", dest="is_global", action="store_true",
                        help="the global plans folder instead of a repository")
    parser.add_argument("--global-root", type=Path, help="the global plans folder (default: hal2's plans.toml)")
    sub = parser.add_subparsers(dest="command", required=True)
    p_new = sub.add_parser("new")
    p_new.add_argument("title")
    p_new.add_argument("--goal", default="")
    p_new.add_argument("--research", action="store_true")
    p_new.add_argument("--no-current", action="store_true")
    p_new.add_argument("--fetch", action="store_true")
    p_new.add_argument("--manual-landing", action="store_true",
                       help="write `Landing: manual`: the plan waits for the user's /mtm at its end")
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
    p_landing = sub.add_parser("landing")
    p_landing.add_argument("landing", choices=LANDINGS)
    p_landing.add_argument("--plan")
    sub.add_parser("check")
    args = parser.parse_args(argv)

    try:
        if args.is_global or args.global_root:
            return run_global(args)
        root = args.root.resolve() if args.root else find_root(Path.cwd())
        if args.command == "check":
            return plan_number.main(["--root", str(root), "check"])
        if args.command == "new":
            result = describe(root, new_plan(root, args.title, args.goal, not args.no_current, args.fetch,
                                             args.research, "manual" if args.manual_landing else "auto"))
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
            elif args.command == "landing":
                set_landing(path, args.landing)
            else:
                set_grilled(path)
            result = describe(root, path)
    except PlanError as error:
        print(f"plan.py: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def run_global(args) -> int:
    """The commands on the global plans folder: no git, no CURRENT_PLAN."""
    folder = (args.global_root or global_folder()).expanduser().resolve()
    root = use_global(folder)
    if args.command == "new":
        result = describe(root, new_global_plan(folder, args.title, args.goal, args.research))
    elif args.command == "list":
        result = [describe(root, p) for p in plan_files(root)]
    elif args.command in ("status", "grilled"):
        if not args.plan:
            raise PlanError("a global plan has no current plan: name it with --plan <n>")
        path = resolve(root, args.plan)
        if args.command == "status":
            set_status(path, args.step, args.status)
        else:
            set_grilled(path)
        result = describe(root, path)
    else:
        raise PlanError(f"'{args.command}' works on a repository only: global plans have no CURRENT_PLAN")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

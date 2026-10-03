#!/usr/bin/env python3
"""What the owner runs this round: every duty and OWNER-ROLE.md task that is due by its rhythm.

  due.py due [--repo <dir>] [--json]
      the due duties and tasks (each with its rhythm and when it last ran) and the loop's
      tick: the shortest rhythm, at least 5 minutes
  due.py ran <name> [--repo <dir>]
      record that a duty or task ran now (runs.jsonl)
  due.py rhythms [--repo <dir>] [--json]
      every duty and task with its rhythm and last run

A rhythm is `round` (every round), `<n>m`, `<n>h`, `hourly`, `daily HH:MM` (also `day, HH:MM`).
Duties take theirs from OWNER-ROLE.md's front matter `rhythm:` (default: every duty `15m`, ci
`30m`, autoclear `1h`), and tasks from their `- **Every**:` line. Reads <repo>/OWNER-ROLE.md (of the
current checkout); writes only ~/skills/owner/<repo>/runs.jsonl.
"""

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DATA = Path(os.environ.get("OWNER_DIR", Path.home() / "skills/owner"))
DUTIES = ("mtm", "lead", "ci", "watch", "autoclear")
DEFAULT_RHYTHM = {"mtm": "15m", "lead": "15m", "ci": "30m", "watch": "15m", "autoclear": "1h"}
MIN_TICK = 5


def parse_rhythm(text: str) -> tuple[str, int | tuple[int, int]]:
    """('round', 0) | ('every', minutes) | ('daily', (hour, minute)); ValueError for anything else."""
    t = text.strip().lower()
    if t in ("round", "every round"):
        return "round", 0
    if t in ("hourly", "hour", "1 hour"):
        return "every", 60
    m = re.fullmatch(r"(\d+)\s*(m|min|minutes?|h|hours?)", t)
    if m:
        n = int(m.group(1))
        return "every", n * 60 if m.group(2).startswith("h") else n
    m = re.fullmatch(r"(?:daily|day,?|once a day,?)\s*(?:at\s*)?(\d{1,2}):(\d\d)", t)
    if m:
        return "daily", (int(m.group(1)), int(m.group(2)))
    if t in ("daily", "day", "once a day"):
        return "daily", (9, 7)
    raise ValueError(f"unknown rhythm {text!r}: use round, 15m, 1h, hourly or daily HH:MM")


def is_due(rhythm: str, last: dt.datetime | None, now: dt.datetime) -> bool:
    kind, value = parse_rhythm(rhythm)
    if kind == "round":
        return True
    if isinstance(value, int):
        return last is None or now - last >= dt.timedelta(minutes=value) - dt.timedelta(seconds=90)
    hour, minute = value
    slot = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return now >= slot and (last is None or last < slot)


def front_matter(text: str) -> dict:
    m = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    try:
        import yaml
        return yaml.safe_load(m.group(1)) or {}
    except ImportError:  # a flat `key: value` and one level of `rhythm:` mapping
        out, current = {}, None
        for line in m.group(1).splitlines():
            line = line.split(" #")[0].rstrip()
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            key, _, value = line.strip().partition(":")
            if line.startswith((" ", "\t")) and current is not None:
                out[current][key] = value.strip()
            elif value.strip():
                out[key] = value.strip()
            else:
                current = key
                out[key] = {}
        return out


def tasks(text: str) -> dict[str, str]:
    """`### <name>` under `## Tasks`, each with its `**Every**` line (default: hourly)."""
    body = text.split("\n## Tasks", 1)
    if len(body) < 2:
        return {}
    section = re.split(r"\n## (?!#)", body[1], maxsplit=1)[0]
    out = {}
    for block in re.split(r"\n### ", "\n" + section)[1:]:
        name = block.splitlines()[0].strip()
        every = re.search(r"\*\*Every\*\*:\s*(.+)", block)
        out[name] = (every.group(1).strip().rstrip(".") if every else "hourly")
    return out


def schedule(role_text: str) -> dict[str, str]:
    """name → rhythm for the enabled duties (`duty:<name>`) and the tasks (`task:<name>`)."""
    fm = front_matter(role_text)
    duties = fm.get("duties") or list(DUTIES)
    if isinstance(duties, str):
        duties = [d.strip() for d in duties.strip("[]").split(",") if d.strip()]
    rhythms = {**DEFAULT_RHYTHM, **(fm.get("rhythm") or {})}
    out = {f"duty:{d}": str(rhythms.get(d, "15m")) for d in duties}
    out.update({f"task:{name}": every for name, every in tasks(role_text).items()})
    return out


def tick(rhythms: dict[str, str]) -> int:
    minutes = [v for kind, v in (parse_rhythm(r) for r in rhythms.values()) if kind == "every" and isinstance(v, int)]
    return max(MIN_TICK, min(minutes or [15]))


def toplevel(repo: str) -> Path:
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=repo, capture_output=True, text=True).stdout
    return Path(out.strip() or repo)


def repo_name(repo: str) -> str:
    common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=repo,
                            capture_output=True, text=True).stdout.strip()
    return Path(common).parent.name if common else Path(repo).name


def last_runs(repo: str) -> dict[str, dt.datetime]:
    f = DATA / repo_name(repo) / "runs.jsonl"
    out: dict[str, dt.datetime] = {}
    if f.exists():
        for e in map(json.loads, f.read_text().splitlines()):
            out[e["name"]] = dt.datetime.fromisoformat(e["at"])
    return out


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("due", "rhythms"):
        x = sub.add_parser(name)
        x.add_argument("--repo", default=os.getcwd())
        x.add_argument("--json", action="store_true")
    r = sub.add_parser("ran")
    r.add_argument("name")
    r.add_argument("--repo", default=os.getcwd())
    args = p.parse_args(argv)

    if args.cmd == "ran":
        d = DATA / repo_name(args.repo)
        d.mkdir(parents=True, exist_ok=True)
        with (d / "runs.jsonl").open("a") as f:
            f.write(json.dumps({"at": dt.datetime.now().isoformat(timespec="seconds"), "name": args.name}) + "\n")
        return 0
    role = toplevel(args.repo) / "OWNER-ROLE.md"
    try:
        rhythms = schedule(role.read_text() if role.exists() else "")
        for r in rhythms.values():
            parse_rhythm(r)
    except ValueError as e:
        print(f"due.py: OWNER-ROLE.md: {e}", file=sys.stderr)
        return 1
    now, last = dt.datetime.now(), last_runs(args.repo)
    rows = [{"name": n, "rhythm": r, "last": last[n].isoformat() if n in last else None,
             "due": is_due(r, last.get(n), now)} for n, r in rhythms.items()]
    if args.cmd == "due":
        rows = [x for x in rows if x["due"]]
    result = {"role_file": role.exists(), "tick_minutes": tick(rhythms), "items": rows}
    if args.json:
        print(json.dumps(result, indent=1))
    else:
        print(f"tick {result['tick_minutes']} min" + ("" if role.exists() else " (no OWNER-ROLE.md: defaults)"))
        for x in rows:
            print(f"- {x['name']:40} {x['rhythm']:14} last {x['last'] or 'never'}" + ("  DUE" if x["due"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

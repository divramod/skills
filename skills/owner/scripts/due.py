#!/usr/bin/env python3
"""What the owner runs this round: the duties and tasks OWNER-ROLE.md opts in to, due by their cron.

  due.py due [--repo <dir>] [--json]
      the due duties and tasks (each with its cron and last run) and the owner loop's cron
  due.py ran <name> [--repo <dir>]
      record that a duty (`duty:<name>`) or task (`task:<name>`) ran now (runs.jsonl)
  due.py check [--repo <dir>] [--json]
      validate OWNER-ROLE.md: every duty and task with a valid cron, the required settings
  due.py list [--repo <dir>] [--json]
      every opted-in duty and task with its cron, last run and whether it is due

Nothing is implicit: only the duties under the front matter's `duties:` (name → cron) and the
tasks under `## Tasks` (each `### <name>` with its `- **Cron**: <cron>` line) run, and the
settings `worker_limit` and `notify` are required. No OWNER-ROLE.md: nothing runs (exit 3).
A cron is standard 5-field notation in local time: minute hour day-of-month month day-of-week
(`*/15 * * * *`, `0 * * * *`, `7 9 * * *`, `0 8 * * 1-5`). An item is due when one of its fire
times passed since it last ran. Writes only ~/skills/owner/<repo>/runs.jsonl.
Exit 0 ok, 1 invalid OWNER-ROLE.md, 3 no OWNER-ROLE.md.
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
NOTIFY = ("every-round", "hourly", "daily", "never")
MIN_TICK = 5
LOOKBACK = dt.timedelta(days=8)
RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))


def parse_field(text: str, lo: int, hi: int) -> set[int]:
    out: set[int] = set()
    for part in text.split(","):
        m = re.fullmatch(r"(\*|\d+(?:-\d+)?)(?:/(\d+))?", part)
        if not m:
            raise ValueError(f"bad cron field {text!r}")
        rng, step = m.group(1), int(m.group(2) or 1)
        if rng == "*":
            a, b = lo, hi
        elif "-" in rng:
            a, b = map(int, rng.split("-"))
        else:
            a = b = int(rng)
            if m.group(2):
                b = hi
        if not (lo <= a <= hi and lo <= b <= hi and a <= b and step > 0):
            raise ValueError(f"cron field {text!r} out of range {lo}-{hi}")
        out.update(range(a, b + 1, step))
    return out


def parse_cron(text: str) -> tuple:
    fields = text.strip().strip("`").split()
    if len(fields) != 5:
        raise ValueError(f"cron {text!r} needs 5 fields: minute hour day-of-month month day-of-week")
    minute, hour, dom, month, dow = (parse_field(f, lo, hi) for f, (lo, hi) in zip(fields, RANGES))
    if 7 in dow:
        dow = (dow - {7}) | {0}
    return minute, hour, dom, month, dow, (fields[2] != "*", fields[4] != "*")


def fires_at(cron: tuple, t: dt.datetime) -> bool:
    minute, hour, dom, month, dow, (dom_set, dow_set) = cron
    if t.minute not in minute or t.hour not in hour or t.month not in month:
        return False
    on_dom, on_dow = t.day in dom, (t.weekday() + 1) % 7 in dow
    return (on_dom or on_dow) if dom_set and dow_set else (on_dom and on_dow)


def last_fire(cron_text: str, now: dt.datetime) -> dt.datetime | None:
    """The most recent fire time at or before `now` (within LOOKBACK)."""
    cron = parse_cron(cron_text)
    t = now.replace(second=0, microsecond=0)
    end = t - LOOKBACK
    while t > end:
        if fires_at(cron, t):
            return t
        t -= dt.timedelta(minutes=1)
    return None


def interval_minutes(cron_text: str) -> int:
    """The shortest gap between two fire times over the next day (a weekly one: a day)."""
    cron, t = parse_cron(cron_text), dt.datetime(2026, 1, 5)
    fires = [t + dt.timedelta(minutes=i) for i in range(24 * 60) if fires_at(cron, t + dt.timedelta(minutes=i))]
    if len(fires) < 2:
        return 24 * 60
    return min(int((b - a).total_seconds() // 60) for a, b in zip(fires, fires[1:]))


def is_due(cron_text: str, last: dt.datetime | None, now: dt.datetime) -> bool:
    fire = last_fire(cron_text, now)
    return fire is not None and (last is None or last < fire)


def front_matter(text: str) -> dict:
    m = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    try:
        import yaml
        return yaml.safe_load(m.group(1)) or {}
    except ImportError:  # flat `key: value` plus one level of mapping
        out, current = {}, None
        for line in m.group(1).splitlines():
            line = re.sub(r"\s+#.*$", "", line).rstrip()
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            key, _, value = line.strip().partition(":")
            value = value.strip().strip("\"'")
            if line.startswith((" ", "\t")) and current is not None:
                out[current][key] = value
            elif value:
                out[key] = value
            else:
                current = key
                out[key] = {}
        return out


def tasks(text: str) -> dict[str, str | None]:
    """`### <name>` under `## Tasks` → its `**Cron**` (None when the line is missing)."""
    body = text.split("\n## Tasks", 1)
    if len(body) < 2:
        return {}
    section = re.split(r"\n## (?!#)", body[1], maxsplit=1)[0]
    out = {}
    for block in re.split(r"\n### ", "\n" + section)[1:]:
        name = block.splitlines()[0].strip()
        cron = re.search(r"\*\*Cron\*\*:\s*`?([^`\n]+?)`?\s*$", block, re.M)
        out[name] = cron.group(1).strip() if cron else None
    return out


def schedule(role_text: str) -> tuple[dict[str, str], dict, list[str]]:
    """(name → cron of every opted-in duty and task, settings, problems)."""
    fm, problems = front_matter(role_text), []
    duties = fm.get("duties") or {}
    if not isinstance(duties, dict):
        problems.append("`duties:` must map each duty to its cron, e.g. `mtm: \"*/15 * * * *\"`")
        duties = {}
    items = {}
    for name, cron in duties.items():
        if name not in DUTIES:
            problems.append(f"unknown duty {name!r} (known: {', '.join(DUTIES)})")
        items[f"duty:{name}"] = str(cron)
    for name, cron in tasks(role_text).items():
        if cron is None:
            problems.append(f"task {name!r} has no `- **Cron**:` line")
        else:
            items[f"task:{name}"] = cron
    for name, cron in items.items():
        try:
            parse_cron(cron)
        except ValueError as e:
            problems.append(f"{name}: {e}")
    settings = {k: fm.get(k) for k in ("worker_limit", "notify")}
    if not isinstance(settings["worker_limit"], int) and not str(settings["worker_limit"]).isdigit():
        problems.append("`worker_limit:` (a number) is required")
    if settings["notify"] not in NOTIFY:
        problems.append(f"`notify:` is required: one of {', '.join(NOTIFY)}")
    return items, settings, problems


def loop_cron(items: dict[str, str]) -> str:
    """The owner loop's cron: every <shortest interval> minutes (at least 5), off the :00 mark."""
    minutes = max(MIN_TICK, min([interval_minutes(c) for c in items.values()] or [15]))
    if minutes >= 60:
        return "4 * * * *"
    if 60 % minutes:
        minutes = next(m for m in (5, 6, 10, 12, 15, 20, 30) if m >= minutes)
    return f"{minutes // 2 or 1}-59/{minutes} * * * *"


def git_out(args: list[str], repo: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True).stdout.strip()


def repo_name(repo: str) -> str:
    common = git_out(["rev-parse", "--path-format=absolute", "--git-common-dir"], repo)
    return Path(common).parent.name if common else Path(repo).name


def last_runs(repo: str) -> dict[str, dt.datetime]:
    f = DATA / repo_name(repo) / "runs.jsonl"
    out: dict[str, dt.datetime] = {}
    if f.exists():
        for e in map(json.loads, f.read_text().splitlines()):
            out[e["name"]] = dt.datetime.fromisoformat(e["at"])
    return out


def record_run(repo: str, name: str, at: dt.datetime | None = None) -> None:
    d = DATA / repo_name(repo)
    d.mkdir(parents=True, exist_ok=True)
    with (d / "runs.jsonl").open("a") as f:
        f.write(json.dumps({"at": (at or dt.datetime.now()).isoformat(timespec="seconds"), "name": name}) + "\n")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("due", "check", "list"):
        x = sub.add_parser(name)
        x.add_argument("--repo", default=os.getcwd())
        x.add_argument("--json", action="store_true")
    r = sub.add_parser("ran")
    r.add_argument("name")
    r.add_argument("--repo", default=os.getcwd())
    args = p.parse_args(argv)

    if args.cmd == "ran":
        record_run(args.repo, args.name)
        return 0
    role = Path(git_out(["rev-parse", "--show-toplevel"], args.repo) or args.repo) / "OWNER-ROLE.md"
    if not role.exists():
        print(f"due.py: no {role}: nothing is opted in, the owner does nothing (template: templates/OWNER-ROLE.md)",
              file=sys.stderr)
        return 3
    items, settings, problems = schedule(role.read_text())
    if problems:
        print(json.dumps({"ok": False, "problems": problems}, indent=1) if args.json else
              "OWNER-ROLE.md problems:\n" + "\n".join(f"- {x}" for x in problems), file=None if args.json else sys.stderr)
        return 1
    now, last = dt.datetime.now(), last_runs(args.repo)
    rows = [{"name": n, "cron": c, "last": last[n].isoformat() if n in last else None,
             "due": is_due(c, last.get(n), now)} for n, c in items.items()]
    if args.cmd == "due":
        rows = [x for x in rows if x["due"]]
    result = {"ok": True, "loop_cron": loop_cron(items), "settings": settings,
              "items": [] if args.cmd == "check" else rows}
    if args.json:
        print(json.dumps(result, indent=1))
    else:
        print(f"OWNER-ROLE.md ok; owner loop cron `{result['loop_cron']}`; {settings}")
        for x in result["items"]:
            print(f"- {x['name']:40} {x['cron']:16} last {x['last'] or 'never'}" + ("  DUE" if x["due"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

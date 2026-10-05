"""The user's decisions in the farmer's log, and which a later one replaced (skills plan 0009).

  farmer.py decision list [--slot <slot>] [--all] [--repo <dir>]
      the current `decision` entries (with --all also the superseded ones, marked), one line each
  farmer.py decision supersede <at>... --by <at> [--why <text>] [--dry-run] [--repo <dir>]
      mark decisions replaced by a later one: appends a `supersede` entry; `<at>` is a prefix of a decision's id

The log is append-only (the tick writes it too), so a mark is a new entry, never an edit of the old one: any entry's
`supersedes` key (an id or a list of them) marks those decisions as replaced, and a decision check never reports
them. A decision's id is its `at`; decisions sharing an `at` (the farmer logs several at once) are `<at>#1`, `<at>#2`
in log order, which an append-only log keeps stable.
"""

import mtm_scan


def ident(log: list[dict]) -> list[tuple[str, dict]]:
    """(id, entry) of every `decision` entry, in log order."""
    ds = [e for e in log if e.get("kind") == "decision"]
    counts: dict[str, int] = {}
    for e in ds:
        counts[e["at"]] = counts.get(e["at"], 0) + 1
    seen: dict[str, int] = {}
    out = []
    for e in ds:
        seen[e["at"]] = seen.get(e["at"], 0) + 1
        out.append((e["at"] if counts[e["at"]] == 1 else f"{e['at']}#{seen[e['at']]}", e))
    return out


def superseded(log: list[dict]) -> set[str]:
    """The ids marked as replaced (a bare `at` marks every decision of that `at`)."""
    marks: set[str] = set()
    for e in log:
        s = e.get("supersedes")
        marks.update([s] if isinstance(s, str) else s if isinstance(s, list) else [])
    return {i for i, e in ident(log) if i in marks or e["at"] in marks}


def decisions(log: list[dict], include_superseded: bool = False) -> list[dict]:
    gone = superseded(log)
    return [{**e, "id": i} for i, e in ident(log) if include_superseded or i not in gone]


def find(log: list[dict], prefix: str) -> dict:
    hits = [e for e in decisions(log, True) if e["id"].startswith(prefix)]
    if len(hits) != 1:
        found = ", ".join(e["id"] for e in hits[:5])
        raise ValueError(f"{prefix}: {'no' if not hits else len(hits)} decisions match{': ' + found if hits else ''}; "
                         f"give a longer id")
    return hits[0]


def mark(log: list[dict], ats: list[str], by: str, why: str) -> dict:
    """The `supersede` entry for decisions `ats` replaced by the later decision `by`; ValueError when one is wrong."""
    new = find(log, by)
    old = [find(log, a) for a in ats]
    late = [e["id"] for e in old if e["at"] >= new["at"]]
    if late:
        raise ValueError(f"--by {new['id']} is not later than {', '.join(late)}")
    slots = ",".join(dict.fromkeys(str(e.get("slot") or "-") for e in old))
    return {"kind": "supersede", "slot": slots, "what": ", ".join(e["id"] for e in old),
            "supersedes": [e["id"] for e in old], "note": f"by {new['id']}" + (f": {why}" if why else ""),
            "by": "farmer"}


def line(e: dict, gone: set[str] | frozenset = frozenset()) -> str:
    return (f"{e['id']} [{e.get('slot') or '-'}]{' (superseded)' if e['id'] in gone else ''} "
            f"{e.get('what', '').strip()[:160]}")


def run(args) -> int:
    main = mtm_scan.main_checkout(args.repo)
    log = mtm_scan.entries(mtm_scan.state_dir(main) / "log.jsonl")
    if args.action == "list":
        import decision_check
        repo = main.rstrip("/").rsplit("/", 1)[-1]
        shown = [e for e in decisions(log, args.all) if not args.slot or decision_check.concerns(e, args.slot, repo)]
        gone = superseded(log)
        print("\n".join(line(e, gone) for e in shown) or "no decisions")
        return 0
    try:
        entry = mark(log, args.at, args.by, args.why)
    except ValueError as e:
        print(f"farmer.py decision supersede: {e}")
        return 1
    for a in entry["supersedes"]:
        print(("would mark " if args.dry_run else "superseded ") + line(find(log, a)))
    print(f"  by {line(find(log, args.by))}")
    if not args.dry_run:
        mtm_scan.log(main, entry)
    return 0

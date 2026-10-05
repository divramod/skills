"""The user's decisions in the farmer's log, and which a later one replaced (skills plan 0009).

  farmer.py decision list [--slot <slot>] [--all] [--repo <dir>]
      the current `decision` entries (with --all also the superseded ones, marked), one line each
  farmer.py decision supersede <at>... --by <at> [--why <text>] [--dry-run] [--repo <dir>]
      mark decisions replaced by a later one: appends a `supersede` entry; `<at>` is a prefix of a decision's `at`

The log is append-only (the tick writes it too), so a mark is a new entry, never an edit of the old one: any entry's
`supersedes` key (an `at` or a list of them) marks those decisions as replaced, and a decision check never reports
them.
"""

import mtm_scan


def superseded(log: list[dict]) -> set[str]:
    out: set[str] = set()
    for e in log:
        s = e.get("supersedes")
        out.update([s] if isinstance(s, str) else s if isinstance(s, list) else [])
    return out


def decisions(log: list[dict], include_superseded: bool = False) -> list[dict]:
    gone = superseded(log)
    return [e for e in log if e.get("kind") == "decision" and (include_superseded or e["at"] not in gone)]


def find(log: list[dict], prefix: str) -> dict:
    hits = [e for e in decisions(log, True) if e["at"].startswith(prefix)]
    if len(hits) != 1:
        raise ValueError(f"{prefix}: {'no' if not hits else len(hits)} decisions match; give a longer `at` prefix")
    return hits[0]


def mark(log: list[dict], ats: list[str], by: str, why: str) -> dict:
    """The `supersede` entry for decisions `ats` replaced by the later decision `by`; ValueError when one is wrong."""
    new = find(log, by)
    old = [find(log, a) for a in ats]
    late = [e["at"] for e in old if e["at"] >= new["at"]]
    if late:
        raise ValueError(f"--by {new['at']} is not later than {', '.join(late)}")
    slots = ",".join(dict.fromkeys(str(e.get("slot") or "-") for e in old))
    return {"kind": "supersede", "slot": slots, "what": ", ".join(e["at"] for e in old),
            "supersedes": [e["at"] for e in old], "note": f"by {new['at']}" + (f": {why}" if why else ""),
            "by": "farmer"}


def line(e: dict, gone: set[str] | frozenset = frozenset()) -> str:
    return (f"{e['at'][:16].replace('T', ' ')} [{e.get('slot') or '-'}]{' (superseded)' if e['at'] in gone else ''} "
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

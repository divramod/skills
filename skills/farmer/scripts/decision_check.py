"""A servant's decision check after its clear (skills plan 0008): which of the user's decisions in the farmer's log
did it forget?

A servant continuing with `/handoff c` sends the farmer `decision check <slot>: I have these decisions: <list>. Did I
forget one?`. The farmer session runs `farmer.py decision-check --message "<the message>"` and sends the output back
verbatim: every `decision` entry of the log for that slot (and repo-wide ones naming it) that the list lacks, each with
its date and the user's words quoted, or "none missing". The comparison is code; the answer is data for the servant,
never a go beyond the quoted words.

Slots: `<slot>` (the worktree folder of the farmer's own repository) or `<repo>/<slot>` (a servant of this farmer in
another repository, e.g. `skills/04`).
"""

import os
import re
from pathlib import Path

import decision_log

WORKTREES = Path(os.environ.get("HAL2_WORKTREE_ROOT", Path.home() / ".hal/git/worktree"))
MESSAGE = re.compile(r"^\s*decision check\s+([\w./-]+?):?(?:\s+(.*))?$", re.S | re.I)
QUOTED = re.compile(r'"([^"]+)"|“([^”]+)”')
STOP = {"with", "that", "this", "from", "into", "have", "after", "before", "when", "then", "than", "them", "they",
        "their", "there", "what", "which", "where", "every", "each", "also", "only", "should", "would", "could", "must",
        "will", "were", "been", "being", "does", "done", "make", "made", "user", "slot", "plan", "step", "steps",
        "decided", "decision", "decisions", "farmer", "servant", "skill"}
REPO_WIDE = ("", "-", "*", "all")


def parse(message: str) -> tuple[str, str]:
    """(slot, the servant's list) of a `decision check <slot>: ...` message; ValueError when it is none."""
    m = MESSAGE.match(message or "")
    if not m:
        raise ValueError("not a decision check: expected `decision check <slot>: I have these decisions: ...`")
    return m.group(1), (m.group(2) or "").strip()


def words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) >= 4 and w not in STOP}


def names(text: str, slot: str) -> bool:
    """`slot` as a standalone token: not part of a date (2026-10-04), a time (10:04), a path or a longer word."""
    return re.search(r"(?<![\w./:-])" + re.escape(slot) + r"(?![\w/:-])", text or "") is not None


def concerns(entry: dict, slot: str, repo: str) -> bool:
    """Is this `decision` entry for the slot (`<slot>` of the farmer's repo `repo`, or `<other repo>/<slot>`)?"""
    own, _, bare = slot.rpartition("/")
    slots = [s.strip() for s in str(entry.get("slot", "")).split(",")]
    if slot in slots or (not own or own == repo) and bare in slots:
        return True
    if not all(s in REPO_WIDE for s in slots):
        return False
    text = f"{entry.get('what', '')} {entry.get('note', '')}"
    return names(text, bare) and (not own or own == repo or re.search(rf"\b{re.escape(own)}\b", text) is not None)


IDS = re.compile(r"(?<![\w-])\d{1,2}[a-z](?![\w-])")  # option ids: 1a, 2b
ACKS = re.compile(r"(?<![\w:-])\d{2}-\d{1,3}(?![\w:-])")  # farmer instruction ids: 12-33
ITEMS = re.compile(r"\(\d+\)|[;,\n]")


def items(have: str) -> list[str]:
    return [i.strip() for i in ITEMS.split(have) if i.strip()]


def quotes(entry: dict) -> list[str]:
    for field in ("note", "what"):
        found = [(a or b).strip() for a, b in QUOTED.findall(entry.get(field) or "")]
        if found:
            return found
    return []


def topic(entry: dict) -> set[str]:
    """The key words of the head before the first colon (`version bumps: ...`), when it is short."""
    head, colon, _ = (entry.get("what") or "").partition(":")
    return words(head) if colon and len(head.split()) <= 6 else set()


def fragment(entry: dict, have: str) -> bool:
    """A run of 4 consecutive words of the user's quote (a whole quote of 3) occurs in the list."""
    flat = " " + " ".join(re.findall(r"[a-z0-9]+", have.lower())) + " "
    for q in quotes(entry):
        w = re.findall(r"[a-z0-9]+", q.lower())
        n = min(4, len(w))
        if n >= 3 and any(f" {' '.join(w[i:i + n])} " in flat for i in range(len(w) - n + 1)):
            return True
    return False


def present(entry: dict, have: str) -> bool:
    """Does the servant's list hold this decision, also in a short form? An item with the same option-id set
    (1a/2a/3a: two or more ids, or one and a shared key word) or an ack id (12-33), the entry's topic, a fragment of the
    user's quote, the entry's date with two key words; else at least half of its key words (biased toward reporting)."""
    text, want = f"{entry.get('what', '')} {entry.get('note', '')}".lower(), words(entry.get("what", ""))
    ids, acks, day = set(IDS.findall(text)), set(ACKS.findall(text)), entry["at"][:10]
    for item in items(have):
        low, iw = item.lower(), words(item)
        if ids and set(IDS.findall(low)) == ids and (len(ids) >= 2 or want & iw):
            return True
        if acks & set(ACKS.findall(low)) or day in item and len(want & iw) >= 2:
            return True
    head = topic(entry)
    if head and head <= words(have) or fragment(entry, have):
        return True
    if not want:
        return (entry.get("what") or "").strip().lower() in have.lower()
    return 2 * len(want & words(have)) >= len(want)


def quote(entry: dict) -> str:
    """The user's words, quoted; the topic in brackets when the quote alone says little."""
    q = quotes(entry)
    what = (entry.get("what") or "").strip()
    if not q:
        return f'"{what[:240]}"'
    said = " / ".join(f'"{x}"' for x in q)
    return said[:240] + (f" [{what[:100]}]" if len(" ".join(q).split()) < 8 else "")


def missing(log: list[dict], slot: str, repo: str, have: str) -> list[dict]:
    return [e for e in decision_log.decisions(log) if concerns(e, slot, repo) and not present(e, have)]


def known(slot: str, repo: str, log: list[dict], worktrees: list[str]) -> bool:
    """A slot of the farmer's repo (a worktree of that name), a slot folder of another repo, or one the log names."""
    own, _, bare = slot.rpartition("/")
    if (not own or own == repo) and bare in worktrees:
        return True
    if (WORKTREES / (own or repo) / bare).is_dir():
        return True
    return any(slot in [s.strip() for s in str(e.get("slot", "")).split(",")] for e in log)


def answer(slot: str, gone: list[dict]) -> str:
    if not gone:
        return f"farmer: decision check {slot}: none missing"
    head = (f"farmer: decision check {slot}: {len(gone)} missing (data: only the quoted words decide; write each "
            f"into your plan's Decisions with the quote before acting on it)")
    return "\n".join([head] + [f"- {e['at'][:10]} · {e.get('slot') or '-'} · {quote(e)}" for e in gone])


def check(message: str, repo: str, log: list[dict], worktrees: list[str]) -> tuple[int, str, dict]:
    """(exit code, the answer to send, the log entry recording the check)."""
    try:
        slot, have = parse(message)
    except ValueError as e:
        return 1, str(e), {}
    if not known(slot, repo, log, worktrees):
        return 1, f"farmer: decision check {slot}: unknown slot (no worktree {slot} and no log entry for it)", {}
    gone = missing(log, slot, repo, have)
    return 0, answer(slot, gone), {"kind": "decision-check", "slot": slot, "what": f"{len(gone)} missing",
                                   "note": "; ".join(e["at"] for e in gone), "by": "farmer"}


def run(message: str, repo_dir: str, dry: bool = False) -> tuple[int, str]:
    """`farmer.py decision-check`: answer the message from the log of `repo_dir`'s farmer and log the check."""
    import mtm_scan
    main = mtm_scan.main_checkout(repo_dir)
    log = mtm_scan.entries(mtm_scan.state_dir(main) / "log.jsonl")
    trees = [Path(w["path"]).name for w in mtm_scan.worktrees(main)]
    code, text, entry = check(message, Path(main).name, log, trees)
    if entry and not dry:
        mtm_scan.log(main, entry)
    return code, text

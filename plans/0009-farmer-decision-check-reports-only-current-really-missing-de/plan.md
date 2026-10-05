# Plan 0009: farmer decision-check reports only current, really missing decisions

Grilled: 2026-10-05 (autogrill ×1)

Landing: auto

Created 2026-10-05. `plans/CURRENT_PLAN` names the active plan; helper files for this plan live next to this file.

## Goal

farmer.py decision-check answers a servant with only the decisions it really lacks: entries a later decision replaced are marked superseded in the log and never reported, short forms (ids like 1a/12-33, a topic, dates, quoted fragments) count as present, and each missing one is one line with date, slot and the user's quote.

## Context

- [Plan 0008](../0008-handoff-asks-for-forgotten-decisions-after-a-clear/plan.md): the decision check this plan
  tightens; `skills/farmer/scripts/decision_check.py`, `farmer.py decision-check`, `test_decision_check.py`
- The farmer's order (farmer-a4, 2026-10-05 ~22:18, relaying the user's "1") with its evidence: on hal2's real log
  the check for `decision check 12: I have these decisions: 1a/2a/3a CI redesign, version bumps` returned 22 missing
- hal2's farmer log `~/skills/farmer/hal2/log.jsonl` (`decision` entries; append-only, the tick writes it too)

## Steps

Each step is detailed when it is next; keep one line per step here. The plan lands once, after all its steps
(`Landing: auto`: the plan skill runs `/mtm` then); steps checked only after the landing come last, their done-when
starting "after the landing: ...".

| # | Step | Done when | Status |
|---|---|---|---|
| 1 | Superseded marks: a `supersedes` key (an `at` or a list of them) on any log entry; `farmer.py decision supersede <at>... --by <at> [--why] [--dry-run]` appends a `supersede` entry; `farmer.py decision list [--slot] [--all]`; the check never reports a superseded entry | `python3 -m unittest test_decision_check` in skills/farmer/scripts: a superseded entry is never reported | done |
| 2 | Short forms count: an entry is present when a list item shares its option-id set (1a/2a/3a) or an ack id (12-33), names its topic (the head before its first colon), holds a 4-word fragment of the user's quote, or names its date with two of its key words; the word overlap stays as the last rule | tests: the farmer's evidence list finds the 1a/2a/3a and version-bump entries present; a real missing one is reported; none missing | done |
| 3 | One line per missing decision: date, slot, the user's quote (the topic in brackets when the quote is short) | tests assert the line format | done |
| 4 | hal2's log: list the superseded candidates as a dry run (recorded below), apply only those clearly replaced by a later entry for the same slot (a repo-wide `-` entry covers every slot), then rerun the slot-12 check | `farmer.py decision list --all` in hal2 shows the marks; the slot-12 output recorded in Notes lists only current, really missing decisions | done |
| 5 | Docs and suites: farmer SKILL.md (decision checks, `decision supersede` when the user replaces a decision), check-plugins, every scripts suite | `python3 scripts/check-plugins.py` ok; farmer and handoff suites pass | done |
| 6 | Write the UATs: `uat.md` beside this file (`plan.py uat`), only the checks a human must do on the default branch after the landing | `plan.py current` shows `uat` with its checks | next |

## Pre-authorized

User-only decisions (money, production deploys, accounts and secrets, paid resources, product choices), asked and
answered before implementation, with the user's words and the date; the run acts on them without asking again.

- <none: the plan needs no user-only decision>

## Decisions

- 2026-10-05 (the user, relayed by the farmer, farmer-a4): tighten `farmer.py decision-check` now as a follow-up plan
  in ~/a/skills (Landing: auto, autogrill once, run to its landing, no questions). User: "1". Must: report only
  decisions no later one replaced (a superseded mark in log.jsonl, a subcommand to set it, hal2's log marked: dry-run
  list first, then only the clearly replaced ones); report only what the list really lacks (key terms, ids, dates,
  quoted fragments); one line each with date, quote, slot; tests (short form present, superseded never reported, a
  real missing one reported, none missing). When landed: send "done: <commit>" and the new slot-12 output.
- 2026-10-05 (autogrill 1): the mark is append-only: a `supersede` entry (`{"kind": "supersede", "slot": <old slot>,
  "what": <old at>, "supersedes": [<at>...], "note": "by <new at>: <why>"}`), and any entry may carry `supersedes`
  itself. Old entries are never rewritten: the tick appends to the same file concurrently.
- 2026-10-05 (autogrill 1): `<at>` arguments match a `decision` entry's `at` by prefix (`2026-10-05T10:46`) and must
  name exactly one; `--by` must name a later decision. The CLI lives in `decision_check.py` (`farmer.py` only
  parses), keeping farmer.py small.
- 2026-10-05 (autogrill 1): id rules are per list item (items split at `(n)`, `;`, `,` and newlines): an option-id
  set counts when it equals the entry's set and either has two or more ids or shares a key word, so "1a/2a/3a" does
  not also cover a slot's older `(1a), (2a)` decision on another subject.
- 2026-10-05 (autogrill 1): "clearly replaced" = a later decision for the same slot (or a repo-wide one) that orders
  the opposite or restates the same rule anew (a newer priority order, a reverted setting, a changed state of the
  user); refinements that add to a decision do not supersede it.

## Notes

- Steps 1-3 share one commit: they rewrite the same functions of `decision_check.py` (supersede marks in the new
  `decision_log.py`).
- Step 4 (hal2's log, before any mark): the slot-12 message returned 20 missing (short forms already counted: the
  1a/2a/3a and version-bump entries were gone); `at` turned out not unique (08:07:38 and 07:12:28 hold two decisions
  each), so ids became `<at>#<n>` for shared ones.
- Step 4 dry-run list (`farmer.py decision supersede ... --dry-run` in ~/a/hal2), with the verdict:
  - applied, by 2026-10-05T16:26:11 ("finish 12 before other things", every other slot pauses until 0131 is
    finished: the same rule restated anew): 2026-10-04T15:26:14 (02 and 10 land now, then 12),
    2026-10-04T17:55:32 (others wait until mtm runs on GitHub Actions), 2026-10-05T10:13:42 (only 12 + helper 10)
  - applied, 2026-10-05T10:46:13 (main.yml cancel-in-progress true) by 2026-10-05T10:48:27 (back to false)
  - applied, 2026-10-05T08:07:38#2 ("I'm not away from the Mac") by 2026-10-05T09:04:56 ("I'm AFK")
  - applied, 2026-10-05T10:16:21 (02 lands right after 09) by 2026-10-05T11:02:44 (02 stops its landing, 12 merges it)
  - applied, 2026-10-03T09:21:36 (slot 11 benchmarks: don't ask again) by 2026-10-05T07:12:28#2 (ask every round
    whether 11 may measure)
  - kept, 2026-10-05T09:02:29 (12's effort High): 09:04:30 asks for "a mix", but 09:04:38's note says High effort is
    fine; a refinement, not a replacement
  - kept, 2026-10-05T10:17:40 (queue cleanup, requeue 00, 07, 06 after 0131): 16:26 does not restate the requeue order
  - kept, 2026-10-04T18:23:29 (runner parked whenever nothing merges): 21:00:20 refines when, it does not replace it
- Step 4 after the marks (7 decisions superseded in hal2's log, `decision list --all` shows them): the farmer's
  message `decision check 12: I have these decisions: 1a/2a/3a CI redesign, version bumps` returns 16 missing (was 22),
  every one current and really absent from that two-item list, one line each (date · slot · quote); the same check
  with all 16 named in short form says "none missing", and `skills/04` with "handoff skill decision check;
  decision-check tightened" says "none missing".
- Step 4 tightened two more rules the live data showed: a repo-wide entry concerns a slot only when its `what` names
  it (a note like "relayed to 12" is bookkeeping), and shared wording counts (4 consecutive words of the decision, or a
  list item of 3+ words with two key words found verbatim in it).

# Plan 0012: the handoff holds every decision

Grilled: 2026-10-06 (autogrill ×1)

Landing: auto

Created 2026-10-06. `plans/CURRENT_PLAN` names the active plan; helper files for this plan live next to this file.

## Goal

A cleared session never loses a user decision and the farmer's decision check reports only real gaps: HANDOFF.md carries a Decisions section indexing every user decision in force (date, quoted words, relaying instruction, home, its end), /handoff c lists from it, and decision_check.py counts a decision present when its quote stands in the asking checkout's HANDOFF.md, current plan or INTENT.md and counts repo-wide entries for a slot only when the slot's work is their subject; a replay of hal2 slot 04's check of 2026-10-06 reports exactly its one real miss.

## Context

- The farmer's brief: `~/.hal/git/worktree/hal2/farmer-hal2/roles/farmer/briefs/2026-10-06-handoff-holds-every-decision.md`
  (hal2 slot 04's decision check of 2026-10-06 10:54: 5 reported missing, 1 really missing)
- [Plan 0008](../0008-handoff-asks-for-forgotten-decisions-after-a-clear/plan.md),
  [0009](../0009-farmer-decision-check-reports-only-current-really-missing-de/plan.md),
  [0010](../0010-decision-check-matches-by-the-relaying-instruction-s-id/plan.md): the decision check this plan
  tightens; [deterministic-first](../../.adr/deterministic-first.md)
- `skills/handoff/SKILL.md` (Write step 1 and 3, Continue step 2), `skills/handoff/scripts/decisions.py`
- `skills/farmer/scripts/decision_check.py` (`present`, `missing`, `run`), `decision_log.py` (`concerns`, `names`,
  `quotes`, `shares_wording`), `skills/farmer/SKILL.md` "Decision checks"

## Steps

Each step is detailed when it is next; keep one line per step here. The plan lands once, after all its steps
(`Landing: auto`: the plan skill runs `/mtm` then); steps checked only after the landing come last, their done-when
starting "after the landing: ...".

| # | Step | Done when | Status |
|---|---|---|---|
| 1 | Handoff (A): `HANDOFF.md` gets a `## Decisions` section, one line per user decision in force for the work (date, the quoted words, who relayed it, its home, `ended <date>: <why>` for one that only held until something happened); `decisions.py` lists it first (plan items it already indexes left out) and `decisions.py --check` validates it (each line: date, quote, home; the home file holds the quote); the Write step's template, rules and a check run, the Continue step, in SKILL.md | `python3 -m unittest discover -s skills/handoff/scripts` passes, with tests for the section's listing and `--check` | done |
| 2 | Decision check reads the checkout (B1): before reporting a decision missing, `decision_check` looks for its quote (normalized: case, whitespace, punctuation; the whole quote of 4+ words or a run of 8 words with 2 key words) in the asking checkout's `HANDOFF.md`, current plan and `INTENT.md`; `run` finds the checkout (own repo: the worktree's path; `<repo>/<slot>`: the worktree root's folder) | `python3 -m unittest test_decision_check` in skills/farmer/scripts: a quote in each of the three files counts present, a missing file or checkout changes nothing | done |
| 3 | Subject, not mention (B2): a repo-wide entry concerns a slot only when its `what` names the slot outside parentheses (an aside such as "(06 ..., 04 plan 0094 step 7, ...)" or "(slot 04)" is no subject); the change's effect on hal2's real log listed in Notes | `python3 -m unittest test_decision_check` passes with the two cases; Notes list every hal2 decision whose concern changed | next |
| 4 | Regression replay (C): fixtures trimmed from hal2 slot 04's `HANDOFF.md`, plan 0094, `INTENT.md` rows and the farmer log at the check; 04's exact message reports exactly "stop the 04-train. 12 should finish first"; with that decision in the fixture handoff's Decisions none missing | `python3 -m unittest test_decision_check` in skills/farmer/scripts: the replay tests pass | |
| 5 | Live: 04's message through `farmer.py decision-check --dry-run --repo ~/a/hal2` on hal2's real log and 04's real checkout, output recorded in Notes | the recorded output reports only the 04-train stop (or none once 04 holds it) | |
| 6 | Docs and suites: farmer SKILL.md "Decision checks" (the checkout's files, subject rule), decision_check docstring, check-plugins, every scripts suite of handoff and farmer | `python3 scripts/check-plugins.py` ok; `python3 -m unittest discover -s skills/farmer/scripts` and the handoff suite pass | |
| 7 | Write the UATs: `uat.md` beside this file (`plan.py uat`), only the checks a human must do on the default branch after the landing | `plan.py current` shows `uat` with its checks | |

## Pre-authorized

User-only decisions (money, production deploys, accounts and secrets, paid resources, product choices), asked and
answered before implementation, with the user's words and the date; the run acts on them without asking again.

- <none: the plan needs no user-only decision>

## Decisions

- 2026-10-06 (the user, relayed by the farmer farmer-hal2-71 in the servant role and brief): "the handoff should
  always contain all decisions. good, that we have this check on continue"; parts A, B, C of the brief in one plan,
  `Landing: auto`, no questions (decided by the repos' rules, recorded here).
- 2026-10-06 (planning): the durable home stays the source of every decision; the handoff's Decisions list is the
  complete index, so the farmer's check and `/handoff c` find every decision in one place.
- 2026-10-06 (autogrill 1): a Decisions line is `- <YYYY-MM-DD> "<the user's words>" (<the user | via farmer <id>>)
  · home: <plan | INTENT.md | .adr/<file>.md | a relative path>[ · ended <YYYY-MM-DD>: <why>]`; `plan` means the
  current plan (its Decisions or Pre-authorized). A decision the user gave as a short answer ("1", "yes") quotes
  it and adds what it chose in brackets after the quote. Only user decisions (direct or relayed) are indexed; the
  plan's autogrill decisions stay in the plan alone.
- 2026-10-06 (autogrill 1): `decisions.py --check` exits 1 when `HANDOFF.md` has no `## Decisions` section (`- none`
  when the work holds no user decision), or a line lacks date, quote or home, names a home file that does not
  exist, or (for a distinctive quote) a home that does not hold the quote; the Write step runs it after writing
  and fixes until it passes. Exit 2 stays git missing.
- 2026-10-06 (autogrill 1): "distinctive" quote matching, the same rule on both sides: text normalized to lower-case
  alphanumeric words; a quote of 4-8 words with a key word must occur whole, a longer one needs a run of 8
  consecutive words holding 2 key words (`words()`: 4+ letters, not a stop word); shorter quotes never count as
  found by text. The rule is a small function in each skill (decisions.py and decision_check.py), since installed
  skills do not import each other; each side tests it.
- 2026-10-06 (autogrill 1): a log entry without a quoted user's words is searched by its `what` under the same
  strict rule; an entry with several quotes is present when any distinctive one is found.
- 2026-10-06 (autogrill 1): the farmer reads exactly the three files of the brief from the asking checkout:
  `HANDOFF.md`, the plan its `plans/CURRENT_PLAN` names (else the plan HANDOFF.md links) and the root `INTENT.md`;
  a missing checkout or file adds nothing (the message alone decides, as before).
- 2026-10-06 (autogrill 1): decisions.py lists the handoff's Decisions first and leaves out a plan item that holds
  one of their distinctive quotes, so the message to the farmer does not repeat a decision.
- 2026-10-06 (autogrill 1): the subject rule strips parentheticals that hold no quote mark before looking for the
  slot in a repo-wide `what`; a slot named in a quote or in the sentence itself still counts. `note` stays out (as
  before).
- 2026-10-06 (autogrill 1): the replay fixtures are trimmed from hal2's files (no hostnames, accounts or run ids:
  the skills repository is public) and live in `skills/farmer/scripts/testdata/slot04/`; the replay uses the farmer
  log as it is now (the stale 2026-10-03 entry superseded at 10:56:39) and also shows that without the supersede
  that entry is reported (the supersede, not text matching, handles stale entries).
- 2026-10-06 (autogrill 1): the live run is `--dry-run` (it must not add a `decision-check` entry to hal2's log).

## Notes

- 04's exact message (step 4's replay and step 5's live run), from its transcript: "decision check 04: I have these
  decisions: plan 0094's Decisions (2026-10-01/02: scope, instances, pinned n8n 2.41.5, writes by diff, webhook-only
  run, backups without the key, hardening, gates without Docker, pane layout, run now, name matching, push rules),
  INTENT.md 2026-10-06 rows (Swift abandoned after the train lands, the cleanup train 04+06,08,11,16,20,22, 09 joins
  before a reland if done and pushed, a red landing keeps the queue). Did I forget one?" (followed by a status line).
- The 5 reported (farmer log 2026-10-06T10:54:29): 2026-10-03T11:23:12 (04, stale: superseded 10:56:39),
  2026-10-05T07:12:28 (`-`, 04 only inside a parenthetical list), 2026-10-05T22:04:13 (`-`, "(slot 04)" of skills),
  2026-10-06T09:39:21 (04, quoted in 04's INTENT.md row), 2026-10-06T10:16:35 (04, the real miss).

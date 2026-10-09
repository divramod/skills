# Plan 0014: The mtm skill and the farmer's merge trains follow hal2's lease and one-train rule

Finished: 2026-10-07

Landing: manual

Created 2026-10-06. `plans/CURRENT_PLAN` names the active plan; helper files for this plan live next to this file.

## Goal

hal2 plan 0169 steps 6 and 11: the mtm skill's finish landing runs without --keep-reserved and waits by PID; the farmer's trains are a trial merge of every waiter behind the current run, the holder as carrier; reserved-idle never fires on a working or dispatching holder.

## Context

- hal2 plan 0169 (`plans/0169-the-merge-queue-is-released-by-code-a-kept-reservation-is-a/plan.md` in hal2, worked
  in its slot 30): decisions 1-19; its steps 6 and 11 are this plan. hal2's `.adr/merge-queue-policy.md` rules 3 and 6.
- The farmer's evidence for `reserved-idle`: hal2's farmer slot, `roles/farmer/log.jsonl` lines 4895-4898
  (2026-10-06 21:37-21:40: instruction 05-40 made slot 05 land between two dispatched land.yml runs).

## Steps

Each step is detailed when it is next; keep one line per step here. The plan lands once, after all its steps
(`Landing: manual`: the plan skill runs `/mtm` then); steps checked only after the landing come last, their done-when
starting "after the landing: ...".

| # | Step | Done when | Status |
|---|---|---|---|
| 1 | Merge trains as a trial merge: `skills/farmer/scripts/trial.py` (`git merge-tree`, soft files), `trains.py` (one train of every waiter with commits, the holder as carrier while its candidate is not pushed, no maximum, a refused waiter left out and named), tests | `python3 -m unittest test_trains` green in `skills/farmer/scripts`, with the queue of 2026-10-06 replayed (05 + 34, 36, 31; 32 without commits out) and a real-git trial merge | done |
| 2 | `reserved-idle` never fires on a holder that works: `mtm_scan.holder_works` (agent busy or active within 15 min, a background shell, subagent or workflow, an unfinished land.yml run: `mtm_ci.unfinished`) | `python3 -m unittest test_mtm_scan test_boss` green, with slot 05's case | done |
| 3 | The docs: merge-train SUBSKILL, instructions/trains.md and mtm.md, the boss's "Merge trains", SKILL.md's duty line | `grep -rn "at most 4" skills/farmer` finds nothing | done |
| 4 | The mtm skill: `--keep-reserved` only when a step follows the landing, the finish landing without it, the lease explained, a background landing waited for by its task notification or PID, never a `pgrep` pattern (SKILL.md steps 4 and 5, references/ci.md) | `grep -c "pgrep" skills/mtm/SKILL.md skills/mtm/references/ci.md` names both | done |
| 5 | All of the repository's script tests | `python3 -m unittest discover -s skills/farmer/scripts` green | done |
| 6 | Land: `/mtm` here, or, while the main checkout holds foreign uncommitted edits to `skills/mtm/references/ci.md`, the patch in hal2's farmer slot `roles/farmer/pending/` and the farmer told (hal2 plan 0169 decision 14) | the change is on `origin/main`, or the patch file exists and the farmer has the line | done |

## Pre-authorized

User-only decisions (money, production deploys, accounts and secrets, paid resources, product choices), asked and
answered before implementation, with the user's words and the date; the run acts on them without asking again.

- None needed.

## Decisions

- 2026-10-06 (the user, via hal2's farmer, instruction 30-23): "its a duty of the farmer to always create the merge
  train for all the queued worktrees behind the current run. in the best case, as now, it combines all waiting
  worktrees into one train."
- 2026-10-07: a waiting ticket with commits rides whatever its plan says (the old `plan_done` test is gone): a ticket
  in the queue says the branch is to land, and a milestone landing has an unfinished plan by design.
- 2026-10-07: the holder carries only as a plain reservation (`held`, `reserved`, no `kept_until`, no landing): an
  active landing, a red candidate's hold and a kept lease are never touched (merge-queue-policy rule 1).
- 2026-10-07: soft conflicts (the waiter still rides): INTENT.md, AGENTS.md, CLAUDE.md, Cargo.lock, the
  workspace-hack, as rule 3 names them.
- 2026-10-07: `Landing: manual`: it lands by step 6, from hal2's plan 0169, not by the plan skill.
- 2026-10-07 (hal2's farmer): the six uncommitted files in the main checkout are nobody's known work: not carried,
  not committed; the farmer asks the user.

## Notes

- Worked from hal2's slot 30 session (plan 0169); this slot has no session of its own.

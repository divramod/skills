---
type: Handoff
schema: 1
plan: 16
title: Handoff of plan 0016
description: Plan 0016's ten steps are done and committed; its landing (/mtm, plans 0015 and 0016) is next, in a fresh session.
status: closed
updated: 2026-10-10
branch: "30"
at: "afcb2a9"
---

# Handoff of plan 0016

The hal2 farmer's servant (farmer-hal2-ac) for the brief plans-coordinator-only-steps-sized. Research plan 0015 is
done (research 0004, [hal2-changes.md](../0015-research-plans-coordinator-only-steps-sized/hal2-changes.md)
sent to the farmer); this implementation plan lands both (`landing: auto`).

## Done

- All ten steps, each run in one subagent and committed by the coordinator: 1 `07406b6`, 2 `8c69a94`, 3 `5186daf`
  (`plan.py prompt`), 4 `7e05745` (plan SKILL.md), 5 `1ae191e` (handoff `drift.py`), 6 `02078a2` (grill), 7
  `ffeed9d` (farmer, create-worktree-session), 8 `85d2267` (sanity-watch, fix-loc, shoot, digest-todolist-picture),
  9 `e9b43b3` (mtm, research, fix-autoclear, README), 10 `afcb2a9` ([uat.md](uat.md), U1-U5).
- `plan.py current`: 10/10, land `ready`; `plan.py check` ok; [D10](decisions.md) added (the sizing rubric's home).
- Handed off before the landing: the coordinator was at 267k tokens, hal2's guard stops near 292k.

## Next

1. `/mtm`: the plan's own landing (`landing: auto`); it lands plans 0015 and 0016 together.
2. Then tell farmer-hal2-ac by SendMessage what landed: plans 0015 and 0016 on the skills repo's main; hal2's part
   stays [hal2-changes.md](../0015-research-plans-coordinator-only-steps-sized/hal2-changes.md) (U5 waits for it);
   hal2-nvim's `shot-template-single.md` item 7 still needs D7's coordinator sentence (digest-todolist-picture's
   `implement.py` adds it meanwhile).

Done when: the landing's merge is on main and slot 30 is reset to it; the farmer has the message.

## Watch out

- Until the landing the installed skills are the main checkout's old ones: `/handoff c` there has no step 0
  (`drift.py`); a clear passes `--effort max` by hand ([D8](decisions.md)).
- Removing the plans/LEAD read-side guards (mtm, farmer, plan.py) is plan 0015 D12's follow-up, not this plan's.
- Never chain a commit after `plan.py check | tail`: the pipe hides the check's failure.
- `research.py check` reports old problems in research docs 0001-0003: not this plan's, never fixed in passing.

## Start with

> /handoff c

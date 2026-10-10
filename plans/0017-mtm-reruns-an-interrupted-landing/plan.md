---
type: Plan
schema: 1
id: 17
title: "mtm reruns an interrupted landing"
description: "mtm reruns merge-to-main or a reserve at once after exit 5 `interrupted` (hal2 0230 adopts it); `stopped` and `cancelled` stay report-and-stop; every doc says so, pinned by a test."
status: done
landing: auto
run: claude-opus-5-5 max 1m
created: 2026-10-10
grilled: 2026-10-10 (autogrill ×1)
finished: 2026-10-10
---

# Plan 0017: mtm reruns an interrupted landing

## Goal

The mtm skill reruns merge-to-main (and a reserve) at once when it ends exit 5 interrupted, its process gone but not stopped by the user, so hal2 plan 0230's rerun adopts the same landing; stopped and cancelled stay report-and-stop; every doc that states the rule says the same, pinned by a test.

## Context

- The brief: farmer-hal2-0d's task 30-39, `~/.hal/git/worktree/hal2/farmer-hal2/roles/farmer/briefs/2026-10-10-mtm-rerun-interrupted.md`
  ([D1](decisions.md)).
- hal2 plan 0230 (hal2 wt 45), its decisions D17-D20 and D23, record `.adr/landings-survive-their-process.md`:
  only a user stop ends a landing `stopped`; a dead process ends it `interrupted`, the queue held, and a rerun of
  merge-to-main adopts it (same landing, ticket and run); a dead waiter's ticket is parked 30 minutes and adopted.
- The docs that state the rule: [mtm SKILL.md](../../skills/mtm/SKILL.md) (lines ~46, ~126, ~192-197, ~205),
  [mtm references/ci.md](../../skills/mtm/references/ci.md) (~60), [plan SKILL.md](../../skills/plan/SKILL.md)
  "Land the plan" (~372).
- The ledgers: [decisions.md](decisions.md), [questions.md](questions.md); the state: [handoff.md](handoff.md).

## Steps

Each step is detailed in `steps/<n>.md`, written when it becomes next (`plan.py status <n> next`); keep one line
per step here. Short and concise: this file at most 150 lines, a cell at most 200 characters, links over repeats. The plan lands once, after all its steps
(`landing: auto`: the plan skill runs `/mtm` then); steps checked only after the landing come last, their done-when
starting "after the landing: ...". Each step runs in one subagent: `Model` (haiku, sonnet, opus, fable), `Effort`
and `Window` (200k, 1m; 1m for the 5.x models) are its own, `Size` its estimated peak context, at most 35% of Window
(`plan.py check`); `run` above is the coordinator's model, effort and window, the session that never does a step.

| # | Step | Done when | Model | Effort | Window | Size | Status |
|---|---|---|---|---|---|---|---|
| 1 | mtm: exit 5 `interrupted` reruns at once (merge-to-main adopts the landing, reserve its ticket); `stopped`, `cancelled` stay report-and-stop: SKILL.md intro, both tables, prose; ci.md | `grep -cE '^. 5 . .interrupted' <file>` prints 2 for skills/mtm/SKILL.md, 1 for its references/ci.md; `hal2-cli-records check` passes | sonnet | high | 1m | 100k | done |
| 2 | The plan skill's "Land the plan" reruns an `interrupted` landing; `skills/mtm/scripts/test_exit_five.bats` pins the split in the three docs | `bats skills/mtm/scripts` passes; the new test fails on the docs of `ef70bf2` | sonnet | medium | 1m | 110k | done |
| 3 | Write the UATs: `uat.md` beside this file (`plan.py uat`), only the checks a human must do on the default branch after the landing | `plan.py current` shows `uat` with its checks | sonnet | medium | 1m | 95k | done |

## Pre-authorized

User-only decisions (money, production deploys, accounts and secrets, paid resources, product choices), asked and
answered before implementation; each is an entry of [decisions.md](decisions.md) with the user's words, named here
by its number. The run acts on them without asking again.

- none: the plan needs no user-only decision; it lands itself at its end (`landing: auto`, the farmer's brief).

## Notes

- Land before hal2 wt 03's plan 0233 freezes the skills repo at its step 9 (the brief); then tell farmer-hal2-0d
  (`ack 30-39: done`).
- The installed skills link into `~/a/skills`, which is behind origin/main (the earlier landing's Q1): run this
  worktree's scripts (`skills/plan/scripts/plan.py`), never the installed ones, while it lasts.

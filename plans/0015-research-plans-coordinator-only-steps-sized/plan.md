---
type: Plan
schema: 1
id: 15
title: "Plans coordinator only steps sized"
description: "Findings per skill and for hal2's autoclear: what must change so a plan's session only coordinates, steps carry Model, Effort and Window under 35%, and the coordinator's values persist."
status: done
landing: manual
run: claude-opus-5-5 max
created: 2026-10-10
grilled: 2026-10-10 (autogrill ×1)
finished: 2026-10-10
---

# Plan 0015: Plans coordinator only steps sized

## Goal

Find, for every skill of this repository and for hal2's autoclear, what must change so that the session running a plan only coordinates (every step in a subagent, no extra sessions), every step row carries Model, Effort and Window and is cut to stay under 35% of that window, and the coordinator's model, effort and window persist in plan.md across a handoff and clear-and-continue.

## Context

- The brief: hal2 farmer's `roles/farmer/briefs/2026-10-10-plans-coordinator-only-steps-sized.md`; the user's words
  are [D1](decisions.md).
- The research doc: [research/0004-plans-coordinator-only-steps-sized](../../research/0004-plans-coordinator-only-steps-sized/research.md),
  each step's findings in its `findings/` folder; hal2's part: [hal2-changes.md](hal2-changes.md).
- The code: [plan skill](../../skills/plan/SKILL.md) (`plan.py`, `parallel.py`, `context.py`, templates),
  [handoff](../../skills/handoff/SKILL.md), [grill](../../skills/grill/SKILL.md); hal2's `hal2-agents` autoclear.
- The ledgers: [decisions.md](decisions.md), [questions.md](questions.md); the state: [handoff.md](handoff.md).

## Steps

Each step is detailed in `steps/<n>.md`, written when it becomes next (`plan.py status <n> next`); keep one line
per step here. Short and concise: this file at most 150 lines, a cell at most 200 characters, links over repeats. The plan lands once, after all its steps
(`landing: auto`: the plan skill runs `/mtm` then); steps checked only after the landing come last, their done-when
starting "after the landing: ...". `Model`, `Effort` and `Window` are the subagent's for the step: this plan
already runs as the plan it researches, the session only coordinates and every step runs in a subagent; `run` above
is the coordinator's. F = `research/0004-plans-coordinator-only-steps-sized/findings/`.

| # | Step | Done when | Model | Effort | Window | Status |
|---|---|---|---|---|---|---|
| 1 | The plan skill: SKILL.md, plan.py, parallel.py, context.py, templates, tests: what changes for coordinator-only runs and sized steps | `test -s F/plan.md` | opus | high | 1m | done |
| 2 | handoff and grill: persisting and restoring the coordinator's model, effort and window; how the autogrill sizes steps | `test -s F/handoff-grill.md` | opus | high | 1m | done |
| 3 | The skills that start sessions or write plans: farmer, create-worktree-session, sanity-watch, fix-loc, shoot, mtm, research | `test -s F/session-skills.md` | opus | high | 1m | done |
| 4 | Every other skill: a line each, what (if anything) changes | `test -s F/other-skills.md` | sonnet | medium | 1m | done |
| 5 | hal2 (read only): where the effort is lost across handoff, clear and continue; the window the guard assumes | `test -s F/hal2.md` | opus | high | 1m | done |
| 6 | Claude Code facts: the Agent tool's model and effort, a subagent's window, /clear, /effort, --effort, effortLevel | `test -s F/claude-code.md` | sonnet | high | 1m | done |
| 7 | Write research.md from the findings and hal2-changes.md beside this plan; send hal2-changes.md to the hal2 farmer | `research.py check` passes and `test -s plans/0015-*/hal2-changes.md` | opus | high | 1m | done |

## Pre-authorized

User-only decisions (money, production deploys, accounts and secrets, paid resources, product choices), asked and
answered before implementation; each is an entry of [decisions.md](decisions.md) with the user's words, named here
by its number. The run acts on them without asking again.

- none: a research plan in this repository; the hal2 change goes to the hal2 farmer, who starts its servant.

## Notes

- Steps 1-6 run at once in subagents (read only, each writes its findings file); step 7 waits for them.
- The implementation plan follows this one in this slot and lands both (`landing: auto` there).

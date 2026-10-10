---
type: Plan
schema: 1
id: 16
title: "Plans coordinator only steps sized"
description: "A plan's session only coordinates: steps run in subagents at checked Model, Effort, Window and Size; the coordinator's values persist in run across clears."
status: open
landing: auto
run: claude-opus-5-5 max 1m
created: 2026-10-10
grilled: 2026-10-10 (autogrill ×1)
---

# Plan 0016: Plans coordinator only steps sized

## Goal

A plan's session is its coordinator only: every step runs in one subagent at its row's Model, Effort and Window, sized under 35% of that window and checked by plan.py; the coordinator's own model, effort and window persist in plan.md's run key across a handoff and clear-and-continue; the servant starters, watchers and other skills follow.

## Context

- The research: [research 0004](../../research/0004-plans-coordinator-only-steps-sized/research.md): its **Findings**
  are this plan's change list (one subsection per area, files and line ranges), its findings/ the details.
- The decisions it builds on: research plan 0015's [decisions.md](../0015-research-plans-coordinator-only-steps-sized/decisions.md)
  (D1 the user's words, D6-D17 the design); hal2's part: [hal2-changes.md](../0015-research-plans-coordinator-only-steps-sized/hal2-changes.md),
  sent to farmer-hal2-ac on 2026-10-10.
- The ledgers: [decisions.md](decisions.md), [questions.md](questions.md); the state: [handoff.md](handoff.md).

## Steps

Each step is detailed in `steps/<n>.md`, written when it becomes next (`plan.py status <n> next`); keep one line
per step here. The plan lands once, after all its steps (`landing: auto`). This plan already runs as the plan skill
it builds: the session is the coordinator (`run` above) and never does a step itself; each step runs in one subagent
at the row's Model and Effort, sized (Size: estimated peak context) under 35% of its Window ([D1](decisions.md)).
R = research 0004's Findings.

| # | Step | Done when | Model | Effort | Window | Size | Status |
|---|---|---|---|---|---|---|---|
| 1 | `session.py`: the session's live model, effort and window with their sources; context.py uses it (5.x = 1m) and reports `effort` and `drift` against `run` (R: plan skill, handoff) | `python3 -m unittest discover -s skills/plan/scripts` passes; `context.py` here shows window 1000000 and effort max | opus | high | 1m | 180k | done |
| 2 | plan.py: Window and Size columns, `run: <model> <effort> <window>`, the `plan-steps-sized` check of open rows, `run --sync\|--check`, `new` writes live values, `migrate`, the template; tests | unittest passes; `plan.py check` refuses a fixture plan whose open row lacks Window | opus | high | 1m | 220k | done |
| 3 | Steps run in subagents: `plan.py prompt <n>` prints the Agent call; parallel.py and plan.py lose slot assignment, LEAD writing, brief, report, reports, watch; the LEAD refusal stays; tests | unittest passes; `plan.py prompt 1` on a fixture prints model, effort and `Plan <NNNN> row 1: ...` | opus | high | 1m | 220k | done |
| 4 | plan SKILL.md and templates: the coordinator-only run (loop, sizing, `run --sync`, check), parallel plans as parallel subagents, subservant sections cut to the guard note; description, call table | `hal2-cli-records check` passes; `grep -c -i subservant skills/plan/SKILL.md` is at most 4 | opus | high | 1m | 200k | next |
| 5 | handoff: `/handoff` runs `plan.py run --sync` before writing; `/handoff c` runs `run --check` and switches once on drift; `/handoff clear` passes `--effort` from `run`; tests | `python3 -m unittest discover -s skills/handoff/scripts` passes | opus | high | 1m | 180k | |
| 6 | grill: the autogrill sets Model, Effort, Window and Size per row by the sizing rubric and splits a step over 35% of its window | `grep -c Size skills/grill/SKILL.md` is at least 2; `hal2-cli-records check` passes | sonnet | high | 1m | 120k | |
| 7 | farmer, create-worktree-session: coordinator sentence, `--model`/`--effort` in servant prompts and orphan restarts; lead_scan skips sessions with background tasks; create.py drops `--lead`, `--base` | the farmer's and create-worktree-session's unittests pass | opus | high | 1m | 250k | |
| 8 | fix-loc, sanity-watch, shoot: the coordinator sentence and explicit `--model`/`--effort` (fix-loc stays Sonnet); sanity-watch's idle classes skip sessions with background tasks; tests | each skill's unittest passes | opus | high | 1m | 220k | |
| 9 | The rest: fix-autoclear (effort from `run`, the hal2 change), research (rows carry the columns, deep mode as a Workflow step), README rows of plan, handoff, pause, continue, list-free-worktrees | `python3 -m unittest discover -s scripts` passes; `plan.py check` passes | sonnet | medium | 1m | 150k | |
| 10 | Write the UATs: `uat.md` beside this file (`plan.py uat`), only the checks a human must do on the default branch after the landing | `plan.py current` shows `uat` with its checks | sonnet | medium | 1m | 100k | |

## Pre-authorized

User-only decisions (money, production deploys, accounts and secrets, paid resources, product choices), asked and
answered before implementation; each is an entry of [decisions.md](decisions.md) with the user's words, named here
by its number. The run acts on them without asking again.

- none: the plan needs no user-only decision; it lands itself at its end (`landing: auto`).

## Notes

- Steps 7, 8 and 9 touch disjoint skills and run as parallel subagents once step 6 is done ([D3](decisions.md)).
- Until hal2's change lands, this plan's own clear-and-continue passes `--effort max` (the coordinator's `run`):
  hal2 would type `/effort medium` otherwise ([D8](decisions.md)).
- The installed skills come from the main checkout: a session continued with `/handoff c` reads the old plan skill,
  so the handoff says how this plan runs.

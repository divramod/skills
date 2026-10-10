---
type: Handoff
schema: 1
plan: 16
title: Handoff of plan 0016
description: Where plan 0016 stands, steps 1-2 done and committed, step 3 is next, the coordinator hands off at 34%.
status: open
updated: 2026-10-10
branch: "30"
at: "8c69a94"
---

# Handoff of plan 0016

The hal2 farmer's servant (farmer-hal2-ac) for the brief plans-coordinator-only-steps-sized. Research plan 0015 is
done (research 0004, [hal2-changes.md](../0015-research-plans-coordinator-only-steps-sized/hal2-changes.md)
sent to the farmer); this implementation plan lands both (`landing: auto`).

## Done

- Plan created, autogrilled (D1-D9), committed; the hal2 brief sent to farmer-hal2-ac.
- Step 1 (`07406b6`): `session.py` reads the live model, effort and window; context.py uses it (5.x = 1m), `drift`.
- Step 2 (`8c69a94`): Window and Size columns, `run: <model> <effort> <window>`, the `plan-steps-sized` check
  (`sizing.py`), `plan.py run --sync|--check` and `migrate`; 110 tests green.
- The coordinator handed off at 33.9% (hal2's guard trips near 292k tokens and would type `/effort medium`).

## Next

1. Step 3: write the `## Task` of [steps/3.md](steps/3.md) (research 0004 Findings "The plan skill", findings/plan.md
   items 4-5: `plan.py prompt <n>` prints the Agent call; parallel.py loses slot assignment, LEAD writing, brief,
   report, reports and watch; the LEAD refusal stays), then its subagent with [step-prompt.md](step-prompt.md).
2. Steps 4-6 in order, then 7, 8 and 9 as parallel subagents ([D3](decisions.md)), then 10; each: done-when,
   review, commit, table, `plan.py run --sync`, `context.py`.
3. The plan's end: `/mtm` (lands plans 0015 and 0016), then tell farmer-hal2-ac by SendMessage what landed.

Done when: `plan.py current` shows 10/10 and `land` ready, then the landing.

## Watch out

- **How this plan runs**: The session is the coordinator only ([D1](decisions.md)): it never does a step itself. For each step: write the
  step file's `## Task` (`plan.py status <n> next` scaffolds it), start one subagent with
  [step-prompt.md](step-prompt.md) (from step 3 on: `plan.py prompt <n>`) at the row's Model and Effort, then run the
  done-when yourself, review the diff, commit the step's files (`... (plan 0016 step <n>)`), `plan.py status <n> done`
  and `<n+1> next`, `context.py`. The installed plan skill (main checkout) still describes the old way: this file wins.
- A clear-and-continue passes `--effort max` (the coordinator's `run`): `hal2-cli-agents clear-and-continue
  --effort max --detach --json` ([D8](decisions.md)); hal2 would type `/effort medium` otherwise.
- Never chain a commit after `plan.py check | tail`: the pipe hides the check's failure.
- Step 1's subagent printed `ANTHROPIC_API_KEY` into its own local transcript while listing the env (told the user;
  nothing in the repo): a step prompt never lists the whole environment.
- `research.py check` reports old problems in research docs 0001-0003: not this plan's, never fixed in passing.

## Start with

> /handoff c

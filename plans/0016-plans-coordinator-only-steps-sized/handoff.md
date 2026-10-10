---
type: Handoff
schema: 1
plan: 16
title: Handoff of plan 0016
description: Where plan 0016 stands, research done (plan 0015), step 1 runs in a subagent, steps 2-10 to go.
status: open
updated: 2026-10-10
branch: "30"
at: "e58518f"
---

# Handoff of plan 0016

The hal2 farmer's servant (farmer-hal2-ac) for the brief plans-coordinator-only-steps-sized. Research plan 0015 is
done (research 0004, [hal2-changes.md](../0015-research-plans-coordinator-only-steps-sized/hal2-changes.md)
sent to the farmer); this implementation plan lands both (`landing: auto`).

## Done

- Plan created, autogrilled (D1-D9), committed.
- Step 1 (session.py, context.py) was running in a subagent at this handoff: check `git status` for its edits and
  its step file's Notes; when they are complete, verify its done-when and commit it, else rerun the step.

## Next

1. Steps 2-6 in order, then 7, 8 and 9 as parallel subagents ([D3](decisions.md)), then 10.
2. The plan's end: `/mtm` (the mtm skill from the main checkout), which lands plans 0015 and 0016.
3. Tell farmer-hal2-ac by SendMessage when the landing is done (plan, commits, what hal2 still has to do).

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
- `research.py check` reports old problems in research docs 0001-0003: not this plan's, never fixed in passing.

## Start with

> /handoff c

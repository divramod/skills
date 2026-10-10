---
type: Decisions
schema: 1
plan: 16
title: Decisions of plan 0016
description: Every decision taken while plan 0016 was planned and run, with who decided and their words.
status: open
---

# Decisions of plan 0016

<!-- One entry per decision, appended, numbered on, never deleted or reworded; only an entry's state and its Record
  and By lines ever change:

  ## D<n> · <YYYY-MM-DD> · <user | farmer | lead | agent> · <in-force | promoted | superseded | ended <YYYY-MM-DD>>

  **D:** <the decision in one line>
  **Words:** "<the words of whoever decided, quoted>"       (required unless `agent`)
  **Via:** <who relayed the user's words, e.g. farmer 44-1>  (optional)
  **Why:** <the reason, a few lines at most>                 (optional)
  **From:** Q<n>                                             (when a question of questions.md led to it)
  **Record:** <a link to the decision record, .adr/<slug>.md>  (exactly when `promoted`)
  **By:** D<m>                                               (exactly when `superseded`)
-->

## D1 · 2026-10-10 · user · in-force

**D:** The plan's session coordinates only and every step runs in a subagent with model, effort and window, under 35% of that window; the coordinator's values persist in plan.md across the handoff and clear-and-continue.
**Words:** "it always tells the agent which creates the plan and runs the plan to be the coordinator of the steps [...] every step should have model effort and context window size And the session planner or coordinator is never doing a step itself it always uses sub agents not extra sessions anymore [...] I think it is good to persist that in the plan file."
**Via:** farmer-hal2-ac, brief `2026-10-10-plans-coordinator-only-steps-sized.md`; in full: plan 0015's D1

## D2 · 2026-10-10 · agent · in-force

**D:** Research 0004 and plan 0015's D6-D17 bind this plan's steps; they are built, not decided again.
**Why:** The research plan decided the design; this plan implements it (plan skill: an implementation plan has no research steps).

## D3 · 2026-10-10 · agent · in-force

**D:** Steps 7, 8 and 9 run as parallel subagents once step 6 is done; the coordinator commits each on its own.
**Why:** They touch disjoint skills (farmer and create-worktree-session; fix-loc, sanity-watch and shoot; the rest).

## D4 · 2026-10-10 · agent · in-force

**D:** The live-values reader is `skills/plan/scripts/session.py`, used by context.py, plan.py and the handoff's scripts.
**Why:** One reader, one test file; context.py already holds half of it (`session_model`).

## D5 · 2026-10-10 · agent · in-force

**D:** `plan-steps-sized` checks the open rows of record-format plans only; done rows and legacy plans pass. `plan.py migrate` brings a running record plan over: missing columns added, Model and Effort from its old `run`, Window from the model, Size `?` until estimated, `run` from the live values.
**Why:** `/handoff` and `/mtm` run `plan.py check`; a running plan meets the rule at its next handoff, a finished one never breaks.

## D6 · 2026-10-10 · agent · in-force

**D:** A step's Model is one of the Agent tool's `haiku|sonnet|opus|fable`; `run`'s model may be a full id. Effort `low|medium|high|xhigh|max`, Window `200k|1m`, Size `<n>k` or `<n>m`, at most 35% of Window (70k, 350k).
**Why:** Steps run through the Agent tool, whose `model` takes aliases only (research 0004, findings/claude-code.md).

## D7 · 2026-10-10 · agent · in-force

**D:** The coordinator sentence, the same in the plan skill and every servant prompt: "You are the plan's coordinator: you never do a step yourself; each step runs in one subagent at its row's Model and Effort, sized under 35% of its Window; you check its done-when, commit it and keep `run` current."
**Why:** One wording to grep for and keep in sync (steps 4, 7, 8).

## D8 · 2026-10-10 · agent · in-force

**D:** Until hal2's change lands, a coordinator's clear-and-continue passes `--effort` from its `run` (this plan: max).
**Why:** hal2 types `[autoclear] effort` (medium) otherwise; `--effort` already overrides it (plan 0015, findings/hal2.md).

## D9 · 2026-10-10 · agent · in-force

**D:** A step's subagent edits but never commits, pushes or lands; it writes its step file's `## Approach` first and `## Notes` at its end, and its final reply is at most 15 lines: the files changed, the done-when's result, follow-ups. `plan.py prompt` prints this prompt.
**Why:** The coordinator verifies and commits each step; short reports keep its context small.

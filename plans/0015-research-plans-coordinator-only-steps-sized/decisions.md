---
type: Decisions
schema: 1
plan: 15
title: Decisions of plan 0015
description: Every decision taken while plan 0015 was planned and run, with who decided and their words.
status: open
---

# Decisions of plan 0015

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

**D:** A plan's session is its coordinator only: every step runs in a subagent, never in an extra session; every step carries model, effort and context window and stays under 35% of that window; the coordinator's model, effort and window persist in plan.md across a handoff and clear-and-continue.
**Words:** "I think I would like to change the plan skill now in a way that it always tells the agent which creates the plan and runs the plan to be the coordinator of the steps and that the single steps should be planned in a way that they never extend the 35% of the context window for the respective model and effort and context window size so every step should have model effort and context window size And the session planner or coordinator is never doing a step itself it always uses sub agents not extra sessions anymore [...] The most important thing is that the plans are always correct and and have the model effort and window in the steps. [...] after the handoff and the clear, the effort level was changed to medium so I think we should also ensure that that the handoff updates the current plans, model, effort, and context window size [...] I think it is good to persist that in the plan file."
**Via:** farmer-hal2-ac, brief `roles/farmer/briefs/2026-10-10-plans-coordinator-only-steps-sized.md` (hal2)

## D2 · 2026-10-10 · agent · in-force

**D:** Two plans in slot 30: this research plan (landing manual), then the implementation plan, whose `landing: auto` lands both.
**Why:** The global rule research-has-a-research-plan, and the plan skill: research big enough to change a plan's shape is a research plan of its own first; an implementation plan has no research steps.

## D3 · 2026-10-10 · agent · in-force

**D:** This plan already runs as the one it researches: the session coordinates only; steps 1-6 run at once in read-only subagents, each writing one findings file; step 7 synthesizes them in a subagent too.
**Why:** The user's goal (D1); it also tests the design on this plan and keeps the coordinator's context small.

## D4 · 2026-10-10 · agent · in-force

**D:** hal2 is read only from here: its exact change goes into `hal2-changes.md` in this plan's folder and to the hal2 farmer by SendMessage, who starts a hal2 servant.
**Why:** The brief's scope: hal2 is another repository.

## D5 · 2026-10-10 · agent · in-force

**D:** A step's Window is written `200k` or `1m` (the two context windows Claude Code offers); step 6 confirms what a subagent can get.
**Why:** Short cells, the units the statusline and context.py use.

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

## D6 · 2026-10-10 · agent · in-force

**D:** A step's Window is a sizing budget, not a launch parameter: the window of the step's model, `1m` for the 5.x models (Claude Code's default; 200k only under `CLAUDE_CODE_DISABLE_1M_CONTEXT=1` or a model without 1M). Supersedes the 200k cells of this plan's rows: they read 1m.
**Why:** findings/claude-code.md: the Agent tool takes no window; this session (`claude-opus-5-5`, no `[1m]`) holds 225k tokens without compacting.

## D7 · 2026-10-10 · agent · in-force

**D:** The 35% budget counts the subagent's whole context, its fixed start (about 85k for a general-purpose subagent) included; a step's `Size` is its estimated peak context, and `plan.py check` refuses Size over 35% of Window.
**Why:** What fills the window is what degrades a step and what a transcript measures; with 1m windows a step keeps about 265k for its own work. This plan's steps peaked at 92k-211k (9-21%).

## D8 · 2026-10-10 · agent · in-force

**D:** Model, Effort, Window and Size are columns of the step table, required in every row of a record-format plan (no fallback to `run`); a legacy plan keeps passing untouched.
**Why:** The user: "the plans are always correct and have the model effort and window in the steps"; a column is checkable before the step is next.

## D9 · 2026-10-10 · agent · in-force

**D:** The coordinator's values live in the front matter key `run: <model> <effort> <window>` (no new key); `plan.py new` writes the session's live values, `plan.py run --sync` updates them.
**Why:** findings/plan.md: hal2's records spec rejects an unknown key (`spec:unknown-key`), `run` is a free string.

## D10 · 2026-10-10 · agent · in-force

**D:** Before a clear the live session wins, after it the plan wins: the coordinator syncs `run` at every step boundary and `/handoff` syncs it before writing; `/handoff c` compares and, when model or effort differ, restarts once through `hal2-cli-agents switch`. Live values: effort from the transcript's last main-chain `effort`, else `$CLAUDE_EFFORT`, else the process's `--effort`, else settings; model as context.py's `session_model`; window from `requestedModel`'s `[1m]` or the 5.x default.
**Why:** The user: "when I change the effort level for a plans coordinator it stays after the hand of clear continue pipe"; both readers verified in this session (`effort: max`, `CLAUDE_EFFORT=max`).

## D11 · 2026-10-10 · agent · in-force

**D:** hal2's clear-and-continue (also when its guard or sweep starts it) restores the effort from the plan's `run`, else the level the session runs at; `[autoclear] effort` becomes the last fallback. hal2 never writes plan.md: only the skills do.
**Why:** findings/hal2.md: the job typed `/effort medium` over a live `max` (pane %10, 08:35:15 and 08:54:41). The user's 2026-10-06 medium wish is kept for sessions nothing else names.

## D12 · 2026-10-10 · agent · in-force

**D:** No new subservant sessions: the plan skill's subservant parts and create.py's `--lead` go; a parallel plan runs ready steps as parallel subagents (Needs/Touches stay). The read-side guards (mtm's subservant-guard.sh, the farmer's plans/LEAD skips, plan.py's refusal) stay until no slot holds plans/LEAD; a follow-up removes them.
**Why:** findings/session-skills.md: hal2's slots 31-33 still carry plans/LEAD of hal2 plan 0149; removing the guards first could let a stale slot land.

## D13 · 2026-10-10 · agent · in-force

**D:** The coordinator never implements: each step goes to one subagent (`Plan <NNNN> row <n>: <title>`, the row's model and effort), which edits but never commits; the coordinator checks the done-when, reviews the diff, commits the step and updates the table. `/mtm milestone` and the Workflow tool (research's deep mode) stay as step runners.
**Why:** D1; the global rule subagent-names-plan-row; milestones serve running plans such as hal2 0149.

## D14 · 2026-10-10 · agent · in-force

**D:** A coordinator waiting on background subagents is not stopped: the farmer's lead_scan `idle-in-plan` and sanity-watch's idle classes skip a session whose `background_tasks` (hal2-cli-agents list --json) is not empty.
**Why:** findings/session-skills.md: idle-while-subagents-run becomes the normal state of every plan session.

## D15 · 2026-10-10 · agent · in-force

**D:** The servant starters (farmer delegation, fix-loc, sanity-watch, shoot) pass explicit `--model` and `--effort` and tell the servant it is its plan's coordinator; fix-loc's coordinator stays Sonnet (its own rule), others default to the user's opus medium unless the brief names more.
**Why:** findings/session-skills.md: none passes them today, so a restart cannot know them; the user, 2026-10-09: "new sessions should always set the effort level to medium and the model to opus 5.5".

## D16 · 2026-10-10 · agent · in-force

**D:** context.py takes the 5.x models' window as 1m (`[1m]`-less ids included, unless `CLAUDE_CODE_DISABLE_1M_CONTEXT=1`) and reports drift between the session and the plan's `run`.
**Why:** It measured this session against 200k (93%) while it ran in 1m (17%).

## D17 · 2026-10-10 · agent · in-force

**D:** hal2-changes.md also asks hal2 to resolve `[autoclear] tokens` against each session's own window (the lower of tokens and percent stops), as hal2 research 0048 intended.
**Why:** findings/hal2.md: `tokens` is converted against settings.json's 200k `opus`, so it never applies.

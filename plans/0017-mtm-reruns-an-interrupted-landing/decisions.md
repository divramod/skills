---
type: Decisions
schema: 1
plan: 17
title: Decisions of plan 0017
description: Every decision taken while plan 0017 was planned and run, with who decided and their words.
status: open
---

# Decisions of plan 0017

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

## D1 · 2026-10-10 · farmer · in-force

**D:** mtm reruns merge-to-main at once after exit 5 `interrupted` (it adopts the same landing); exit 5 `stopped` or `cancelled` stays report-and-stop; the own-shell-time-limit exception stays; a small plan, autogrilled once, no questions, `landing: auto`.
**Words:** "exit 5 + `interrupted` (its shell or process went away, not the user): rerun merge-to-main at once; it adopts the same landing. Say so in one line. - exit 5 + `stopped` or `cancelled` stays as it is: the user ended it, report and stop, never rerun."
**Via:** farmer-hal2-0d, task 30-39, from the user's decision Q11a of 2026-10-10 (agent sessions and landings survive a tmux crash, hal2 plan 0230)

## D2 · 2026-10-10 · agent · in-force

**D:** (autogrill 1) Besides the brief's three spots, mtm's intro ("never again after it ended with exit 5", ~46), mtm's CI table (references/ci.md ~60) and the plan skill's "Land the plan" (~372) state the rule and change with it; delete-worktree-session's "a landing ends with exit 5 and must be rerun" and the handoff skill's reserve-rerun line already agree and stay.
**Why:** a doc still saying "never rerun after exit 5" would contradict the tables; a landing through CI reads ci.md's table, not SKILL.md's.

## D3 · 2026-10-10 · agent · in-force

**D:** (autogrill 1) The reserve table's exit 5 `interrupted` reruns the same reserve at once too: it takes its parked ticket's place back.
**Why:** hal2 0230 D20 parks a dead waiter's ticket for 30 minutes and its rerun adopts the place; the brief names both tables.

## D4 · 2026-10-10 · agent · in-force

**D:** (autogrill 1) The landing table's `stopped` row no longer names SIGTERM among its causes, only the Stop button and `worktree stop`; report-and-stop stays.
**Why:** hal2 0230 D17: a bare SIGTERM (a dying session, a tmux crash) ends a landing `interrupted`; only a stop request, or SIGINT at a tty, ends it `stopped`.

## D5 · 2026-10-10 · agent · in-force

**D:** (autogrill 1) No hal2 version check: with a hal2 older than plan 0230 the rerun takes the held queue over and lands anew (mtm's intro: a failed or interrupted landing holds the queue until the worktree's next merge-to-main), so "rerun at once" holds for both.
**Why:** one rule for every installed hal2; the JSON's `adopted` only shows on the new one.

## D6 · 2026-10-10 · agent · in-force

**D:** (autogrill 1) The pin is a bats test beside mtm's others, `skills/mtm/scripts/test_exit_five.bats`: each exit-5 row naming `interrupted` says rerun and names neither `stopped` nor `cancelled`; the plan skill's "Land the plan" no longer counts `interrupted` among the user's stops.
**Why:** no test pinned the tables (the brief: update any that does); the farmer's test_never_idle.py pins documented wording the same way, and mtm's scripts are tested with bats.

## D7 · 2026-10-10 · agent · in-force

**D:** (autogrill 1) Nothing new about hal2's sweep typing `/mtm` into a slot whose landing ended `interrupted` (hal2 0230 D22): its reserve answers `kept: true` (held for the interrupted landing) and its merge-to-main adopts, as the changed tables say.
**Why:** step 1's row for `kept: true` ("an earlier failed or interrupted landing") already covers it.

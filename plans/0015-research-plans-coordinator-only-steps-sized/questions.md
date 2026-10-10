---
type: Questions
schema: 1
plan: 15
title: Questions and answers of plan 0015
description: Every question asked while plan 0015 ran, the agent's and the user's, each with its answer.
status: closed
---

# Questions and answers

<!-- One entry per question, appended, numbered on, never deleted; each clear on its own: plain words, what it is
about, what each answer causes:

  ## Q<n> · <YYYY-MM-DD> · <agent | user> · <open | answered <YYYY-MM-DD> | dropped <YYYY-MM-DD>>

  **Q:** <the question; the user's own words quoted>
  **A:** <the answer; the user's own words quoted when the user gave it>   (an open entry has no A line)
  **Decision:** D<n>                                                      (when the answer is a decision)
-->

## Q1 · 2026-10-10 · agent · answered 2026-10-10

**Q:** Does "35% of the window" count a step subagent's fixed start (about 85k tokens here), or only the step's own work?
**A:** The whole context, start included; with 1m windows a step keeps about 265k for its own work (decided as D7 of decisions.md).

## Q2 · 2026-10-10 · agent · answered 2026-10-10

**Q:** Can a subagent be given a 1m window, given that the Agent tool's model takes only opus, sonnet, haiku or fable?
**A:** It gets its model's window, 1m for the 5.x models; Window is a sizing budget, not a launch option (decided as D6 of decisions.md).

## Q3 · 2026-10-10 · agent · answered 2026-10-10

**Q:** Should the user's `[autoclear] effort = "medium"` still apply when a plan or a live level names another effort, and who writes a changed effort back into plan.md?
**A:** Only as hal2's last fallback; only the skills write plan.md (the coordinator and /handoff with `plan.py run --sync`) (decided as D11 of decisions.md).

## Q4 · 2026-10-10 · agent · answered 2026-10-10

**Q:** Should hal2's `[autoclear] tokens` ceiling count against each session's own window, so that the lower of tokens and percent stops?
**A:** Yes, as hal2 research 0048 intended; it goes to the hal2 farmer in hal2-changes.md (decided as D17 of decisions.md).

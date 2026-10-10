---
type: UAT
schema: 1
title: "Plans coordinator only steps sized"
description: "The checks a person runs by hand on the default branch after plan 0016 landed."
status: active
plan: 16
created: 2026-10-10
shotfile: plans
---

# UAT 0016: Plans coordinator only steps sized

Before you start: the default branch with plan 0016 landed is installed (`scripts/install-skills.py` run) and hal2
runs, so sessions live in panes you can see (the Agents pane). Use a throwaway repository slot and a small
record plan whose open rows are sized (Model, Effort, Window, Size); its `run` is `opus max 1m`.

<!-- Checks only a human can do; ids are never reused. Verdicts go to uat-results.jsonl, written by the landing. -->

## U1 a started plan runs as its coordinator
Priority: p1
Tags: smoke, regression
Run: python3 ~/skills/plan/scripts/plan.py current

Preconditions:
- A record plan with at least two open rows of different Model and Effort (say sonnet medium and opus high).

Steps:
1. Run `/plan start` in the session and let two steps run.
2. Watch the Agents pane (or the subagent transcripts under the session's folder) while they run.
3. Look at the commits: each carries `(plan NNNN step n)`.

Expected: every step ran in its own subagent at its row's model and effort, described `Plan NNNN row n: ...`; the
coordinator session edited none of the steps' files itself and only committed after checking the done-when.

## U2 a clear in a running plan keeps the plan's effort
Priority: p1
Tags: regression
Run: python3 ~/skills/handoff/scripts/drift.py --clear

Preconditions:
- A plan running in a pane whose `run` has effort max (hal2's own default after a clear is medium).

Steps:
1. In the running plan's session type `/handoff clear`.
2. When the fresh session has started, read its model and effort (`python3 ~/skills/plan/scripts/context.py`, or the
   status line).

Expected: the fresh session runs at `run`'s effort (max), not medium, and continues the plan with `/handoff c`.

## U3 a changed effort is switched back once, with no loop
Priority: p1
Tags: regression

Preconditions:
- A written handoff of a plan with `run` opus max; the session's effort changed by hand (`/effort medium`).

Steps:
1. Run `/handoff c`.
2. Watch the pane: the session restarts once at `run`'s model and effort and continues.
3. Change the effort by hand again and run `/handoff c` for the same handoff.

Expected: the first `/handoff c` switches once; the second does not switch again but syncs `run` to the session's
values and says so in its first report. No restart loop.

## U4 a farmer servant starts with the ROLE's model and effort
Priority: p2
Tags: regression

Preconditions:
- `roles/farmer/ROLE.md` of a repository sets `servant_model` and `servant_effort` (say sonnet and low), a
  delegation due.

Steps:
1. Let the farmer's tick delegate a task, or run `/farmer act` on a due delegation.
2. Read the servant pane's model and effort, then its first prompt.

Expected: the servant runs at the ROLE's values (not opus medium) and its prompt holds the sentence "You are the
plan's coordinator: you never do a step yourself; ...". A free session with other values is switched, not reused as is.

## U5 hal2's own clear keeps the plan's effort
Priority: p2
Tags: regression

Preconditions:
- hal2's change in `plans/0015-research-plans-coordinator-only-steps-sized/hal2-changes.md` has landed in hal2 (until then
  this check is expected to fail and stays open).

Steps:
1. Run a plan with `run` effort max until hal2's context guard clears and continues the session by itself.
2. Read the fresh session's effort.

Expected: it is the plan's `run` effort (max), not `[autoclear] effort` (medium).

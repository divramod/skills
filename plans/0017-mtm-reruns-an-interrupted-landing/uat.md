---
type: UAT
schema: 1
title: "mtm reruns an interrupted landing"
description: "The checks a person runs by hand on the default branch after plan 0017 landed."
status: active
plan: 17
created: 2026-10-10
shotfile: mtm
---

# UAT 0017: mtm reruns an interrupted landing

Before you start: hal2 plan 0230 (landings survive their process) is landed and installed, and the installed skills are current (`~/a/skills` at origin/main, after this plan landed). Use a throwaway slot with one small commit. hal2 0230's own U5 checks hal2's sweep typing `/mtm`; it is not repeated here.

<!-- Checks only a human can do: what the plan's own tests and the agent's self-check could not prove (how it looks
and feels on the real setup, real data, other devices). At most ~10, riskiest first (p1 = what the goal promises).
One `## U<n> <title>` per check; ids are never reused. Fields: Priority p1|p2|p3, Tags (comma list; `regression`
carries a check forward to later plans of the feature), Kind scripted|explore, Open (a hal2:// deep link),
Run (a shell command), Timebox + Charter (explore), Preconditions, Steps, Expected. `status` is this file's
(`archived`: its checks are no longer run); the verdicts go to uat-results.jsonl beside it,
written by the landing, never into this file. -->

## U1 A landing whose process dies is rerun at once and adopted
Priority: p1
Tags: regression
Run: hal2-cli-git worktree queue

Preconditions:
- A throwaway slot with one small commit, a Claude session in it, nothing else in the merge queue.

Steps:
1. In the session run `/mtm`; while the landing runs, `kill -HUP` the merge-to-main process (or crash its tmux).
2. Watch the session; do not answer anything.

Expected: the session says in one line that the landing was interrupted and reruns merge-to-main at once, without asking; the rerun's JSON says `adopted` with the same landing id and run as before; one landing, one run, ending landed.

## U2 A user stop is reported and never rerun
Priority: p1
Tags: regression
Run: hal2-cli-git worktree stop

Preconditions:
- Same throwaway slot with a new small commit, nothing else in the queue.

Steps:
1. In the session run `/mtm`; while the landing runs, stop it with `hal2-cli-git worktree stop` (or the Stop button in hal2-macos).

Expected: the session reports the landing as stopped and stops; it does not rerun merge-to-main on its own.

## U3 A dying reserve is rerun and keeps its place
Priority: p2
Run: hal2-cli-git worktree queue

Preconditions:
- hal2 plan 0230 step 7 installed; a second slot holds the queue with a running landing; the throwaway slot has a plan whose reserve waits behind it.

Steps:
1. While the throwaway slot's reserve waits, `kill -HUP` its process.
2. Run `hal2-cli-git worktree queue`.

Expected: the session reruns the reserve at once; the queue shows the same place (the parked ticket adopted), not a new one at the back.

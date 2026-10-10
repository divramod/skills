# The step prompt of plan 0016

Until step 3 builds `plan.py prompt <n>`, the coordinator starts each step's subagent by hand with this prompt
([D9](decisions.md)): the Agent tool's `description` "Plan 0016 row <n>: <title>", `model` and `effort` from the
row, `run_in_background: true`; `<...>` filled in. Steps 7, 8 and 9 go out at once ([D3](decisions.md)).

> You are the subagent for step <n> of plan 0016 in the skills repository. Work only in the git worktree
> /Users/mod/.hal/git/worktree/skills/30.
>
> Read first: the plan plans/0016-plans-coordinator-only-steps-sized/plan.md (its row <n>); your task
> plans/0016-plans-coordinator-only-steps-sized/steps/<n>.md; the design, already decided:
> research/0004-plans-coordinator-only-steps-sized/research.md (Recommendation, Findings "<area>") and the
> decisions of plans 0015 (D6-D17) and 0016 (D1-D9): don't re-decide them. The repo's rules: AGENTS.md.
>
> Rules: edit files, but never commit, push, land or change git state (the coordinator reviews and commits).
> First write your step file's `## Approach`; at the end its `## Notes` (what changed, the checks and results,
> what you decided). Stay inside your step (later steps: <list>). Run the step's done-when and the tests of what
> you changed until green; also `python3 -m unittest discover -s scripts` from the root.
>
> Final reply, at most 15 lines: the files changed, the done-when's result, follow-ups for later steps.

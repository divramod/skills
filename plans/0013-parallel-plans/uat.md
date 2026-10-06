# UAT 0013: parallel plans

Plan: 0013-parallel-plans
Created: 2026-10-06
Shotfile: plan

Before you start: the skills repo's main installed (`python3 scripts/install-skills.py`), hal2 running, and hal2's
02 running its first parallel plan (plan 0149) with at least one subservant started.

<!-- Checks only a human can do: what the plan's own tests and the agent's self-check could not prove (how it looks
and feels on the real setup, real data, other devices). At most ~10, riskiest first (p1 = what the goal promises).
One `## U<n> <title>` per check; ids are never reused. Fields: Priority p1|p2|p3, Tags (comma list; `regression`
carries a check forward to later plans of the feature), Kind scripted|explore, Open (a hal2:// deep link),
Run (a shell command), Timebox + Charter (explore), Preconditions, Steps, Expected. -->

## U1 A subservant starts in slot 30+ and works on its step only
Priority: p1
Tags: smoke, regression
Kind: scripted
Run: cat ~/.hal/git/worktree/hal2/3*/plans/LEAD

Preconditions:
- 02 assigned a step to `slot NN` (`plan.py current` in 02 shows it `running`).

Steps:
1. Look at hal2's Agents pane: the new session sits in a slot 30 or higher, never below.
2. Look at its statusline and pane: it names the lead's plan, and its first prompt is the brief's prompt (no `/mfm`).
3. Watch it until it reports: it commits only its step, pushes `origin/NN` and tells 02 `step <n> reported: ...`.

Expected: the session is in slot 30+, `plans/LEAD` holds `02 <plan> <step>`, it never edits plan.md, never runs
`/mtm`, and 02 merges its report.

## U2 hal2 shows the lead's parallel plan readably
Priority: p1
Tags: regression
Kind: explore
Timebox: 10m
Charter: the plans view with a 7-column step table

Steps:
1. Open plan 0149 of hal2 in hal2-macos's plans view, from 02's checkout.
2. Open it from a subservant's checkout too.

Expected: the Needs, Touches and Who columns read well, a `\|` in a cell shows as `|`, the step statuses
(`running`, `blocked ...`) are visible, and both views show the lead's copy of plan.md.

## U3 A cleared subservant continues its step, not the plan
Priority: p2
Tags: regression
Kind: explore
Timebox: 20m
Charter: a subservant crossing the autoclear threshold

Steps:
1. Wait for (or watch) a subservant whose context passes the autoclear threshold.
2. Read what the fresh session does after `/handoff c`.

Expected: it prints the `lead:` line, goes on with the same step and stops after its report; it never starts the
plan's next step or a landing.

## U4 The farmer leaves subservants out of the landings
Priority: p2
Tags: regression
Kind: explore
Timebox: 15m
Charter: hal2's farmer while subservants hold commits that are not on main

Steps:
1. Watch the farmer's rounds and the merge queue while subservants work.

Expected: no `land now` or `/mtm` reaches a slot with `plans/LEAD`, no `work-not-queued` for it, and a stopped
subservant is restarted only with `/handoff c`.

## U5 A finished slot 30+ is pruned
Priority: p3
Kind: explore
Timebox: 10m
Charter: the farmer's prune after 02 merged a subservant's step

Steps:
1. After 02 merged a slot's report, leave that slot idle for more than an hour.
2. Check hal2's worktree list and `git ls-remote origin <NN>`.

Expected: the farmer removed the worktree and deleted `origin/NN`; slots below 30 and unmerged slots are untouched.

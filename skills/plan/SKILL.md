---
name: plan
description: Lean planning for a repo — one markdown file per plan in docs/plans/<NNNN>-<slug>.md (goal, context links, a step table with a done-when check and status per step, decisions), with docs/plans/CURRENT_PLAN naming the active plan so the statusline shows it. Create a plan, show where it stands, start the next step (offering /grill first when the plan hasn't been grilled), mark steps done, or switch plans. Execution uses the agent's built-ins (plan mode, /goal, subagents), not plan machinery. Use when the user wants to plan a feature, asks what's next on the plan, or finishes a step. `/plan h` shows help.
---

# plan

One file per plan, nothing else: no phase folders, no state files, no gap sub-plans. The plan says *what* and
*in which order*; each step is detailed only when it is next. `S=<skill-dir>/scripts`; every command prints the
plan as JSON (`slug`, `path`, `grilled`, `done`, `total`, `next`, `steps`).

Ask every question with the question tool, recommended option first.

**The step table is the plan's state.** `/plan`, `/handoff` and the statusline all read it; nothing else tracks
progress. Update it the moment a step's check passes, never later.

**Good steps** fit one session (split a step that doesn't) and have a **Done when** that is a runnable command
where possible (`cargo test -p x`, `grep -rn "old" src | wc -l` = 0), otherwise one observable behaviour.

**One home per decision**: decisions that matter only to this plan go under the plan's **Decisions**; decisions
that outlive it go to the repo's decision record (`docs/intent.md` or equivalent) and the plan links them.

## Pick the action

| Call | Short | Does |
|---|---|---|
| `/plan new <idea>` | | [create a plan](#new-plan) and make it current |
| `/plan`, `/plan status` | `/plan s` | [show where the current plan stands](#status) |
| `/plan next` | `/plan n` | [start the next step](#start-the-next-step), offering `/grill` first |
| `/plan done [<step>]` | `/plan d [<step>]` | [finish a step](#finish-a-step) after its check passes |
| `/plan use <slug or number>` | `/plan u <ref>` | `python3 $S/plan.py use <ref>`, then Status |
| `/plan help` | `/plan h` | print this table and stop |

## New plan

1. Understand the idea: read `docs/intent.md` (or the repo's decision record) and the code it touches. Settled
   decisions are not questions. Ask only what you can't find out, with the question tool.
2. Create the file and make it current:
   ```bash
   python3 $S/plan.py new "<title>" --goal "<goal>"
   ```
3. Fill it in: **Context** links, 3–10 good **Steps** (see above), first step `next`, the rest empty. Record
   decisions taken so far in their one home.
4. Show the plan in a few lines, then ask with the question tool: grill it now with `/grill` (recommended for
   anything beyond a small change), start step 1, or stop here.

## Status

```bash
python3 $S/plan.py current      # or: list
```

Report the plan title, `done/total`, the next step and its done-when check, and whether it was grilled. If there is
no current plan, list the plans and ask which one to use.

## Start the next step

1. `python3 $S/plan.py current`, then offer grilling with the question tool, proportionate to the risk:
   - plan not grilled yet (`grilled` empty): `/grill` the whole plan first (recommended), or start anyway;
   - plan grilled, step non-trivial: `/grill q` on this step (one round, top risks), or start;
   - small, clear step: just start.

   On a grill, continue only after it confirms shared understanding.
2. Detail the step: the files it touches, the approach, the tests. For anything non-trivial use plan mode
   (Codex: `/plan`) and let the user approve.
3. Implement. When the done-when is a runnable check, offer to run the step as
   `/goal "<done-when> passes"` so the agent keeps going until it does; use subagents (with worktree isolation)
   for independent parallel parts.
4. When the done-when check passes, [finish the step](#finish-a-step).

## Finish a step

1. Run the step's done-when check yourself and show the result; a step is done only when it passes.
2. Update the step table right away, marking the step and naming the next one:
   ```bash
   python3 $S/plan.py status <step> "done (<short sha>, check passed)"
   python3 $S/plan.py status <next step> next
   ```
3. Record what the step taught under **Notes**, and adjust later steps when reality changed them (say what and
   why; decisions go to their one home).
4. When every step is done, say so and ask whether to set another plan current.

Don't commit or push on your own; `/handoff` commits plan and handoff together before a `/clear`.

---
name: plan
description: Lean planning for a repo — one self-contained folder per plan, plans/<NNNN>-<slug>/plan.md plus the plan's helper files (goal, context links, a step table with a done-when check and status per step, decisions), with plans/CURRENT_PLAN naming the active plan so the statusline shows it; a research plan (research, not implementation) gets the slug <NNNN>-research-<topic>. Create a plan, show where it stands, run it (offering /grill first when the plan hasn't been grilled; once started, it runs step after step autonomously, commits after every step and stops for a /handoff when the context window is 40% full), mark steps done, or switch plans. Execution uses the agent's built-ins (subagents, /goal), not plan machinery. Use when the user wants to plan a feature, asks what's next on the plan, or finishes a step. `/plan h` shows help.
---

# plan

One folder per plan, `plans/<NNNN>-<slug>/`: `plan.md` plus any helper file that belongs to the plan (scripts,
notes, data), so the folder is self-contained; no phase folders, no state files, no gap sub-plans. The plan says *what* and
*in which order*; each step is detailed only when it is next. `S=<skill-dir>/scripts`; every command prints the
plan as JSON (`slug`, `path`, `research`, `grilled`, `done`, `total`, `next`, `steps`).

Ask every question with the question tool, recommended option first.

**`plans/CURRENT_PLAN` names what the worktree works on**, so the statusline shows it: `new` and `use` write the
plan's slug into it. Other work writes it too (a shot `<shotfile>/<n>/<title-slug>`, a task name); then `current` fails with
"not a plan": list the plans and ask, as in Status. The file is gitignored per-worktree state: never stage or
commit it (untrack and gitignore it when the repo still tracks it); `/mtm` deletes it once a finished plan has landed.

**Research plans start with `research`.** When the user asks for research rather than an implementation
(investigate, compare, evaluate, analyse, "find out", "look into": the result is findings or a decision, not code),
create the plan with `--research`: its slug becomes `<NNNN>-research-<topic>`, so `CURRENT_PLAN` and the
statusline show it as research (the number stays first, so numbering and `/plan use <n>` keep working; a title that
already starts with "research" is not prefixed twice). Its deliverable is the research doc
`research/<NNNN>-<topic>/research.md` (numbered on its own, next free number in `research/`), linked under
**Context**; decisions it yields go to their one home. Research that gets no plan writes `research-<topic>` into
`CURRENT_PLAN`. When unsure whether a request is research or implementation, ask.

**The step table is the plan's state.** `/plan`, `/handoff` and the statusline all read it; nothing else tracks
progress. Update it the moment a step's check passes, never later.

**Good steps** fit one session (split a step that doesn't) and have a **Done when** that is a runnable command
where possible (`cargo test -p x`, `grep -rn "old" src | wc -l` = 0), otherwise one observable behaviour.

**Steps checked after the landing belong to `/mtm`.** A step whose done-when needs the landed default branch (its
install or deploy, a check of the installed binary: write it as "after the user's `/mtm`: ...") is not finished
with a commit of its own after the landing: that commit would stay on the worktree branch. `/mtm` finishes it
while it still holds the merge queue and lands it too (its step "Finish the plan and land it"), so the worktree
ends with nothing that is not on the default branch.

**Plan numbers are unique across the whole repository**: `plan.py new` takes the number from
`scripts/plan_number.py`, which looks at every worktree (committed or not), every local and remote-tracking
branch, and a reservation file shared by all worktrees of the clone, and reserves the number under a file lock.
Never pick a number by hand. Add `--fetch` when other machines may have created plans. `python3 $S/plan.py check`
lists numbers used by two plans (for example after merging branches from before this rule).

**One home per decision**: decisions that matter only to this plan go under the plan's **Decisions**; decisions
that outlive it go to the repo's decision record (`INTENT.md` or equivalent) and the plan links them.

## Pick the action

| Call | Short | Does |
|---|---|---|
| `/plan new <idea>` | | [create a plan](#new-plan) and make it current |
| `/plan new --research <topic>` | `/plan r <topic>` | the same for a research plan (see above): slug `<NNNN>-research-<topic>` |
| `/plan`, `/plan status` | `/plan s` | [show where the current plan stands](#status) |
| `/plan next` | `/plan n` | [run the plan](#run-the-plan) from its next step to the end, offering `/grill` first |
| `/plan done [<step>]` | `/plan d [<step>]` | [finish a step](#finish-a-step) after its check passes |
| `/plan use <slug or number>` | `/plan u <ref>` | `python3 $S/plan.py use <ref>`, then Status |
| `/plan check` | `/plan c` | `python3 $S/plan.py check`: report plan numbers used twice |
| `/plan help` | `/plan h` | print this table and stop |

## New plan

1. Understand the idea: read `INTENT.md` (or the repo's decision record) and the code it touches. Settled
   decisions are not questions. Ask only what you can't find out, with the question tool.
2. Create the plan folder with its `plan.md` and make it current:
   ```bash
   python3 $S/plan.py new "<title>" --goal "<goal>"              # add --research for a research plan
   ```
3. Fill it in: **Context** links, 3–10 good **Steps** (see above), first step `next`, the rest empty. A research
   plan's steps end in its research doc (e.g. question and criteria, sources, compare, write `research.md`, record
   the decision). Record
   decisions taken so far in their one home.
4. Show the plan in a few lines, then ask with the question tool: grill it now with `/grill` (recommended for
   anything beyond a small change), [run it](#run-the-plan) from step 1 (it then runs to the end on its own), or
   stop here.

## Status

```bash
python3 $S/plan.py current      # or: list
```

Report the plan title, `done/total`, the next step and its done-when check, and whether it was grilled. If there is
no current plan, list the plans and ask which one to use.

## Run the plan

**Once a plan is started it runs to the end on its own.** The user approves the plan once, when it starts (the
grill offer below); after that, work through the steps one after another without asking for approval, without plan
mode and without per-step grill offers. Ask the user only for

- a decision that is genuinely theirs and not settled by the plan, the decision record (`INTENT.md`), the ADRs or
  the repo's rules for choosing between options (decide those yourself and record them in their one home);
- an outward-facing or irreversible action (pushing, publishing, deleting data that is not the plan's own);
- a step whose done-when check still fails after reasonable attempts: stop and report what fails.

1. `python3 $S/plan.py current`, then offer grilling with the question tool, once, proportionate to the risk:
   - plan not grilled yet (`grilled` empty): `/grill` the whole plan first (recommended), or start anyway;
   - plan grilled: just start (offer `/grill q` only when the next step is risky and was never discussed).

   On a grill, continue only after it confirms shared understanding.
2. For each step, starting with the one marked `next`:
   1. Detail it for yourself: the files it touches, the approach, the tests. Use subagents (with worktree
      isolation) for independent parallel parts.
   2. Implement it until its done-when check passes.
   3. [Finish the step](#finish-a-step): table, notes, commit, context check. Stop when the context check says so,
      otherwise go on with the next step.
3. When every step is done, say so and ask whether to set another plan current. When only steps checked after the
   landing are left, stop there: say that the user's `/mtm` lands the work and finishes them (never start it
   yourself).

## Finish a step

1. Run the step's done-when check yourself and show the result; a step is done only when it passes.
2. Update the step table right away, marking the step and naming the next one:
   ```bash
   python3 $S/plan.py status <step> done
   python3 $S/plan.py status <next step> next
   ```
3. Record what the step taught under **Notes**, and adjust later steps when reality changed them (say what and
   why; decisions go to their one home).
4. **Commit the step**: one commit with the step's changes and the updated plan, message
   `<type>(<scope>): <what> (plan <NNNN> step <n>)`. Stage only the files this step changed (other uncommitted
   work in the tree stays as it was). Never push without the user's consent.
5. **Check the context window**:
   ```bash
   python3 $S/context.py            # --threshold 40 by default; percent as the statusline shows it
   ```
   - `stop` is true (40% or more used): stop the plan here. Run `/handoff` (it records decisions, writes
     `HANDOFF.md` with the plan's next step and commits it), then tell the user to run `/clear` and then
     `/handoff c` to continue.
   - `stop` is false: continue with the next step.
   - `known` is false (not Claude Code, no transcript): judge the fill level yourself and say so; when in doubt,
     stop and hand off.

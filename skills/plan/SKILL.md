---
name: plan
description: Lean planning for a repo — one self-contained folder per plan, plans/<NNNN>-<slug>/plan.md plus the plan's helper files (goal, context links, a step table with a done-when check and status per step, decisions), with plans/CURRENT_PLAN naming the active plan so the statusline shows it; a research plan (research, not implementation) gets the slug <NNNN>-research-<topic>. Create a plan, show where it stands, run it (offering /grill first when the plan hasn't been grilled; once started, it runs step after step autonomously, commits after every step, when the context window passes 35% before a new step, hands off, clears its own session and continues with /handoff c on its own through hal2, and when its last step is done lands itself with /mtm (`Landing: auto`, what `new` writes; `manual` waits for the user's /mtm)), mark steps done, or switch plans. Execution uses the agent's built-ins (subagents, /goal), not plan machinery. Use when the user wants to plan a feature, asks what's next on the plan, or finishes a step. `/plan h` shows help.
---

# plan

One folder per plan, `plans/<NNNN>-<slug>/`: `plan.md` plus any helper file that belongs to the plan (scripts,
notes, data), so the folder is self-contained; no phase folders, no state files, no gap sub-plans. The plan says *what* and
*in which order*; each step is detailed only when it is next. `S=<skill-dir>/scripts`; every command prints the
plan as JSON (`slug`, `path`, `research`, `grilled`, `done`, `total`, `next`, `landing`, `land`, `problems`, `steps`).

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

**A plan lands once, at its end.** `new` writes `Landing: auto` below the title: when the plan's last step is done,
the plan lands itself with `/mtm` in the same run (the user's start of the plan is the consent to land it; hal2's
merge-hooks ADR, "Who starts a landing"). `Landing:
manual` (`new --manual-landing`, `plan.py landing manual`, and every plan without the line) waits for the user's
`/mtm`. So write plans that land only when they are finished:

- no step lands, merges to the default branch or asks for `/mtm` (no "one part per landing"): work that should land
  on its own is a plan of its own;
- a step whose done-when needs the landed default branch (its install or deploy, a check of the installed binary)
  starts its done-when with **"after the landing: ..."** (`after_landing` in the JSON) and comes after every other
  step. `/mtm` finishes it while it still holds the merge queue and lands it too (its step "Finish the plan and
  land it"), never as a commit of its own after the landing, which would stay on the worktree branch. `problems`
  names after-landing steps that other steps follow: move them to the end.

`land` in the JSON says what the plan's end does: `ready` (auto, no open step before the landing: land now), `wait`
(auto, steps before the landing still open), `manual` or `none` (a global plan). `next` is the first open step that
runs before the landing.

**Plan numbers are unique across the whole repository**: `plan.py new` takes the number from
`scripts/plan_number.py`, which looks at every worktree (committed or not), every local and remote-tracking
branch, and a reservation file shared by all worktrees of the clone, and reserves the number under a file lock.
Never pick a number by hand. Add `--fetch` when other machines may have created plans. `python3 $S/plan.py check`
lists numbers used by two plans (for example after merging branches from before this rule).

**One home per decision**: decisions that matter only to this plan go under the plan's **Decisions**; decisions
that outlive it go to the repo's decision record (`INTENT.md` or equivalent) and the plan links them.

**Global plans** belong to no repository: they live in hal2's global plans folder (`plans.toml`'s `root`,
default `~/Documents/hal2/plans`, laid out like `plans/`), and hal2-macos shows them next to every repository's
plans. `-g` goes before the command: `python3 $S/plan.py -g new "<title>"` (numbered and written by
`hal2-cli-plans new --global`, so hal2 must be installed), `-g list`, `-g status <step> <status> --plan <n>`,
`-g grilled --plan <n>`. A global plan has no `CURRENT_PLAN` (no statusline), so always name it (`--plan <n>`),
and its steps are not committed (the folder is no repository) unless the user keeps that folder in git.

## Pick the action

| Call | Short | Does |
|---|---|---|
| `/plan new <idea>` | | [create a plan](#new-plan) and make it current |
| `/plan new --research <topic>` | `/plan r <topic>` | the same for a research plan (see above): slug `<NNNN>-research-<topic>` |
| `/plan new --autogenerated <by> <idea>` | | a plan a watcher made (e.g. sanity-watch): writes `Autogenerated: <by>, <date>`, hal2 marks it `autogenerated` |
| `/plan`, `/plan status` | `/plan s` | [show where the current plan stands](#status) |
| `/plan next` | `/plan n` | [run the plan](#run-the-plan) from its next step to the end, offering `/grill` first |
| `/plan done [<step>]` | `/plan d [<step>]` | [finish a step](#finish-a-step) after its check passes |
| `/plan use <slug or number>` | `/plan u <ref>` | `python3 $S/plan.py use <ref>`, then Status |
| `/plan landing auto\|manual` | `/plan l a\|m` | `python3 $S/plan.py landing <auto\|manual>`: whether the current plan lands itself at its end |
| `/plan new -g <title>` | `/plan r -g <topic>` | a global plan (see "Global plans" above; `--research` works too) |
| `/plan s -g <n>`, `/plan n -g <n>`, `/plan d -g <n> [<step>]` | | status, run, finish a step of global plan `<n>` |
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
   the decision). No step lands; steps checked after the landing come last ("after the landing: ..."). The plan
   lands itself at its end (`Landing: auto`); when the user wants to land it themselves, `plan.py landing manual`.
   Record decisions taken so far in their one home.
4. Show the plan in a few lines, then ask with the question tool: grill it now with `/grill` (recommended for
   anything beyond a small change), [run it](#run-the-plan) from step 1 (it then runs to the end on its own and, `Landing: auto`, lands), or
   stop here.

## Status

```bash
python3 $S/plan.py current      # or: list
```

Report the plan title, `done/total`, the next step and its done-when check, whether it was grilled, whether it lands
itself (`landing`) and any `problems`. If there is
no current plan, list the plans and ask which one to use.

## Run the plan

**An autogenerated plan never asks the user** (`autogenerated` in the JSON is set: a watcher such as
sanity-watch made it, and the user is away): no grill offer (the prompt that started it says how to grill), every
question below is decided by you by the repo's rules and recorded in its home, and when you are blocked you push a
notification naming the plan and stop.

**Once a plan is started it runs to the end on its own, landing included.** The user approves the plan once, when it starts (the
grill offer below); after that, work through the steps one after another without asking for approval, without plan
mode and without per-step grill offers. Ask the user only for

- a decision that is genuinely theirs and not settled by the plan, the decision record (`INTENT.md`), the ADRs or
  the repo's rules for choosing between options (decide those yourself and record them in their one home);
- an outward-facing or irreversible action (pushing, publishing, deleting data that is not the plan's own), except
  the landing of an auto plan at its end ([Land the plan](#land-the-plan)), which the start of the plan agreed to;
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
3. When no step before the landing is left (`land` is `ready`, `manual` or `none`), the plan's end:
   - `ready`: [land the plan](#land-the-plan) now, in this run: no question, no context check, no handoff.
   - `manual`: say the plan is done and that the user's `/mtm` lands it (never start it yourself), and ask whether
     to set another plan current.
   - `none` (a global plan): say it is done.

## Land the plan

The last step of an auto plan is done (`land: ready`). This is the only time the plan skill starts a landing, and
only for the plan the user started (also in a session continued with `/handoff c`); never before its last step,
never for another worktree or session, never again after a landing ended with exit 5 (stopped, cancelled,
interrupted).

1. Check you can land: a worktree on its own branch (in the main checkout or on the default branch there is nothing
   to land: say so and stop), `problems` empty (else move the after-landing steps to the end, commit, check again).
2. Commit and sort before the queue is reserved: everything the plan changed is committed (each step committed
   already); untracked files are junk (gitignore), secrets (gitignore, never commit) or the plan's work (commit);
   what stays unclear is left untracked, no question, and named in the report.
3. Run the [mtm](../mtm/SKILL.md) skill from its step 1, as a plan's landing: it lands the work, finishes the
   after-landing steps, clears `CURRENT_PLAN` and reports what landed. Fix and rerun as it says while it holds the
   queue; when it has to ask the user (the attempts limit, a cause you cannot fix), push a notification first
   (`PushNotification`, e.g. "plan 0063: landing holds the merge queue, needs you"), so the user learns it even when
   away. A successful landing only reports.

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
5. **Check the context window** before starting the next step:
   ```bash
   python3 $S/context.py            # threshold: hal2's agents.toml [autoclear] percent, else 35; percent as the statusline shows it
   ```
   - No step is left that you run now (this was the last step, or only steps checked after the landing remain):
     skip the check, never hand off or clear here: the plan's end ("Run the plan" point 3: the plan lands itself,
     or it is done and the user's `/mtm` lands it) and its report must stay on screen. hal2 refuses to clear then too (`no-open-plan`).
   - `stop` is false: continue with the next step.
   - `stop` is true (and steps are left that you run now): stop the plan here and hand off:
     1. Stop your background work (TaskStop every background shell, subagent, workflow and monitor you started):
        after a clear their notifications would wake the fresh session. Note in the handoff what was stopped and
        must be rerun.
     2. Run `/handoff` (it records decisions, writes `HANDOFF.md` with the plan's next step and commits them).
     3. `autoclear` is true: start the automatic clear-and-continue, then end your turn with one line saying the
        session clears and continues with `/handoff c`; do nothing after it (the clear waits for your turn to end,
        waits out a draft the user types, and never types into a non-empty prompt):
        ```bash
        hal2-cli-agents clear-and-continue --detach --json    # pane from $TMUX_PANE or $HAL2_TERMINAL, session from $CLAUDE_CODE_SESSION_ID
        ```
        `already-running` is fine: hal2's guard already started the job (it stops a session above the threshold at
        its next tool, research 0010 in hal2): just end your turn. When it fails to start otherwise (`no-open-plan`,
        ...), say so and fall back to the next point.
     A tool denied with "hal2: context at N% ... run /handoff now" is that guard: stop the step where it is, do
     points 1-2 (only the hand-off's tools run now; name in the handoff what was cut off), then end your turn: the
     job is already waiting, so skip point 3.
     4. `autoclear` is false (its `autoclear_reason` says why: disabled, not Claude Code, neither in tmux nor a hal2 terminal, no hal2):
        tell the user to run `/clear` and then `/handoff c` to continue.
   - `known` is false (not Claude Code, no transcript): judge the fill level yourself and say so; when in doubt,
     stop and hand off as above.

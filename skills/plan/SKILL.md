---
name: plan
description: Lean planning for a repo — one self-contained folder per plan, plans/<NNNN>-<slug>/plan.md plus the plan's helper files (goal, context links, a step table with a done-when check and status per step, decisions), with plans/CURRENT_PLAN naming the active plan so the statusline shows it; a research plan (research, not implementation) gets the slug <NNNN>-research-<topic>. Create a plan, show where it stands, run it (every new plan gets one autogrill round first, then the offer: run now, another autogrill round, manual grill; once started, it runs step after step autonomously, commits after every step, when the context window passes 35% before a new step, hands off, clears its own session and continues with /handoff c on its own through hal2, and when its last step is done lands itself with /mtm (`Landing: auto`, what `new` writes for an implementation plan; `manual`, every research plan's, waits for the user's /mtm or lands with the implementation plan that follows)), mark steps done, or switch plans. Execution uses the agent's built-ins (subagents, /goal), not plan machinery. Use when the user wants to plan a feature, asks what's next on the plan, or finishes a step. `/plan h` shows help.
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

**A research plan never lands itself.** The user's workflow is research → an implementation plan → its landing:
`new --research` writes `Landing: manual`, so a finished research plan stops at its end (no `/mtm`, not into the
merge queue). Its research doc and decisions reach the default branch with the implementation plan that follows it
in the same worktree (that plan's `Landing: auto` lands both), or when the user runs `/mtm`. Never switch a research
plan to `auto`; only an implementation plan lands itself.

**Every implementation plan ends with its UATs.** Its last step before the landing (the template's "Write the
UATs") writes `plans/<NNNN>-<slug>/uat.md` (`plan.py uat` scaffolds it from `templates/uat.md`): the user acceptance
checks the user runs by hand on the default branch after the landing, in hal2's UAT tab. Only what a human must see
goes there: derive the checks from the goal, each step's done-when and the diff (new panes, commands, keys, deep
links), drop what the plan's tests and your own verification already proved, keep what needs eyes and hands (layout,
feel, real data, other devices), riskiest first (`Priority: p1` = what the goal promises), at most about 10, each
with `Open:` (a hal2:// deep link) or `Run:` (a command) when one exists, steps and the expected result; tag checks
that should come back with later plans of the feature `regression`. Ids (`U1`, `U2`, ...) are never reused.
Results never go into a checkout (hal2 keeps them in its state root); a failed check becomes a shot in the plan's
feature shotfile (`Shotfile:`). A research plan has no UATs (`new --research` leaves the step out).

**The step table is the plan's state.** `/plan`, `/handoff` and the statusline all read it; nothing else tracks
progress. Update it the moment a step's check passes, never later.

**Good steps** fit one session (split a step that doesn't) and have a **Done when** that is a runnable command
where possible (`cargo test -p x`, `grep -rn "old" src | wc -l` = 0), otherwise one observable behaviour.

**A plan lands once, at its end.** `new` writes `Landing: auto` below the title: when the plan's last step is done,
the plan lands itself with `/mtm` in the same run (the user's start of the plan is the consent to land it; hal2's
merge-hooks ADR, "Who starts a landing"). `Landing:
manual` (`new --manual-landing`, every research plan, `plan.py landing manual`, and every plan without the line) waits for the user's
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
| `/plan uat` | | `python3 $S/plan.py uat`: scaffold the current plan's `uat.md` (see above) |
| `/plan landing auto\|manual` | `/plan l a\|m` | `python3 $S/plan.py landing <auto\|manual>`: whether the current plan lands itself at its end |
| `/plan new -g <title>` | `/plan r -g <topic>` | a global plan (see "Global plans" above; `--research` works too) |
| `/plan s -g <n>`, `/plan n -g <n>`, `/plan d -g <n> [<step>]` | | status, run, finish a step of global plan `<n>` |
| `/plan check` | `/plan c` | `python3 $S/plan.py check`: report plan numbers used twice |
| `/plan help` | `/plan h` | print this table and stop |

## New plan

1. Understand the idea: read `INTENT.md` (or the repo's decision record) and the code it touches. Settled
   decisions are not questions. Ask only what you can't find out, with the question tool.
2. **Research before planning.** When the idea needs research (the web, prior art, how others do it, "come up
   with ideas", comparing options, a format or structure to choose), do it now, before any step is written and
   before the autogrill: subagents in parallel, findings in a research doc (`research/<NNNN>-<topic>/research.md`,
   linked under **Context**). Research big enough to change the plan's shape is a research plan of its own first
   (`new --research`); the implementation plan follows it. **An implementation plan has no research steps**: its
   steps and grill decisions build on research that is already done, so nothing it decides is decided blind.
3. Create the plan folder with its `plan.md` and make it current:
   ```bash
   python3 $S/plan.py new "<title>" --goal "<goal>"              # add --research for a research plan
   ```
4. Fill it in: **Context** links, 3–10 good **Steps** (see above), first step `next`, the rest empty. A research
   plan's steps end in its research doc (e.g. question and criteria, sources, compare, write `research.md`, record
   the decision). No step lands; steps checked after the landing come last ("after the landing: ..."). The plan
   lands itself at its end (`Landing: auto`); when the user wants to land it themselves, `plan.py landing manual`.
   Record decisions taken so far in their one home.
5. **Autogrill it once** before offering it: run [`/grill auto`](../grill/SKILL.md#auto) on the plan (one round
   without questions: map the design tree, decide every open branch yourself by the repo's rules, record each
   decision in its home, adjust steps and checks), which stamps `plan.py grilled --auto`.
6. Show the plan and the round's decisions in a few lines, then ask with the question tool, these three options:
   - **Run now** (recommended): [run it](#run-the-plan) from step 1; it runs to the end on its own and, with
     `Landing: auto`, lands;
   - **Another autogrill round**: `/grill auto` again (it looks for what is still open, deeper branches first),
     then this offer again;
   - **Manual grill**: `/grill` with question rounds (the autogrill's decisions are the recommended answers), then
     this offer again after its shared-understanding check.

   Stopping here is the question tool's free answer, not an option.

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

**Once a plan is started it runs to the end on its own, landing included, and never asks the user anything.** The
user approves the plan once, when it starts (the grill offer below); from then on there is no question-tool call,
no approval, no plan mode and no per-step grill offer until the plan's end. What would have been a question:

- **a decision** nothing settles (the plan, the decision record `INTENT.md`, the ADRs, the repo's rules for choosing
  between options): take the more professional, battle-tested option yourself and record it in its one home (the
  plan's **Decisions**, or `INTENT.md` when it outlives the plan);
- **an outward-facing or irreversible action** (pushing, publishing, deleting data that is not the plan's own): skip
  it and name it in the plan's final report; the landing of an auto plan at its end
  ([Land the plan](#land-the-plan)) is not one of these: the start of the plan agreed to it;
- **how to verify** the work: verify it yourself before the landing, never by asking, and never by installing the
  worktree's build for the user to try ("install from the worktree, you test" is not an option): builds, unit and
  snapshot tests, UI tests, running the CLIs and the app's own test paths, fake agents or services in a scratch
  state folder, never the user's live tmux or desktop. What only a human can judge (how it looks and feels on the
  user's real setup) becomes a check in the plan's `uat.md`, which the user runs on the default branch after the
  landing; it never blocks the landing;
- **a step whose done-when check still fails** after reasonable attempts (or a blocker you cannot fix): stop the
  run, push a notification naming the plan and what fails (`PushNotification`), and report; no question.

1. `python3 $S/plan.py current`. A plan that was never grilled (`grilled` empty, e.g. from before this rule) gets
   one `/grill auto` round first; then, unless the user already chose to run it, the same three-option offer as
   [New plan](#new-plan) step 6 (Run now, Another autogrill round, Manual grill). A grilled plan the user asked to run
   just starts. After the start nothing is asked any more (see above).

2. For each step, starting with the one marked `next`:
   1. Detail it for yourself: the files it touches, the approach, the tests. Use subagents (with worktree
      isolation) for independent parallel parts.
   2. Implement it until its done-when check passes.
   3. [Finish the step](#finish-a-step): table, notes, commit, context check. Stop when the context check says so,
      otherwise go on with the next step.
3. When no step before the landing is left (`land` is `ready`, `manual` or `none`), the plan's end:
   - `ready`: [land the plan](#land-the-plan) now, in this run: no question, no context check, no handoff.
   - `manual`: say the plan is done and that the user's `/mtm` (or, for a research plan, the implementation plan
     after it) lands it; never start `/mtm` yourself and ask nothing.
   - `none` (a global plan): say it is done.

## Land the plan

The last step of an auto plan is done (`land: ready`). This is the only time the plan skill starts a landing, and
only for the plan the user started (also in a session continued with `/handoff c`); never before its last step,
never for another worktree or session, never again after a landing ended with exit 5 (stopped, cancelled,
interrupted) by the user (one your own shell tool's time limit ended is rerun: the mtm skill's steps 1 and 4).

1. Check you can land: a worktree on its own branch (in the main checkout or on the default branch there is nothing
   to land: say so and stop), `problems` empty (else move the after-landing steps to the end, commit, check again).
2. Commit and sort before the queue is reserved: everything the plan changed is committed (each step committed
   already); untracked files are junk (gitignore), secrets (gitignore, never commit) or the plan's work (commit);
   what stays unclear is left untracked, no question, and named in the report.
3. Run the [mtm](../mtm/SKILL.md) skill from its step 1, as a plan's landing: it lands the work, finishes the
   after-landing steps, clears `CURRENT_PLAN` and reports what landed. Fix and rerun as it says while it holds the
   queue. Where mtm would ask the user (the attempts limit, a cause you cannot fix), a plan's landing asks
   nothing: push a notification (`PushNotification`, e.g. "plan 0063: landing holds the merge queue, needs you")
   and stop with the report; the failed landing keeps holding the queue until the user acts. A successful landing
   only reports.

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

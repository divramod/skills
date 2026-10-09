---
name: plan
description: Lean planning for a repo — one self-contained folder per plan, plans/<NNNN>-<slug>/plan.md plus the plan's helper files (goal, context links, a step table with a done-when check and status per step, decisions), with plans/CURRENT_PLAN naming the active plan so the statusline shows it; a research plan (research, not implementation) gets the slug <NNNN>-research-<topic>. Create a plan, show where it stands, run it (every new plan gets one autogrill round first, then the offer: run now, another autogrill round, manual grill; once started, it runs step after step autonomously, commits after every step, when the context window passes 35% before a new step, hands off, clears its own session and continues with /handoff c on its own through hal2, and when its last step is done lands itself with /mtm (`Landing: auto`, what `new` writes for an implementation plan; `manual`, every research plan's, waits for the user's /mtm or lands with the implementation plan that follows)), mark steps done, or switch plans. A parallel plan (`new --parallel`: Needs, Touches, Who) runs independent steps at once in subagents and in subservant sessions in worktree slots 30-99 that never land (`ready`, `assign`, `brief`, `report`, `reports`, `watch`); a slot with plans/LEAD does its one step only. Execution uses the agent's built-ins (subagents, /goal), not plan machinery. Use when the user wants to plan a feature, asks what's next on the plan, or finishes a step. `/plan h` shows help.
---

# plan

One folder per plan, `plans/<NNNN>-<slug>/`: `plan.md` plus any helper file that belongs to the plan (scripts,
notes, data), so the folder is self-contained; no phase folders, no state files, no gap sub-plans. The plan says *what* and
*in which order*; each step is detailed only when it is next. `S=<skill-dir>/scripts`; every command prints the
plan as JSON (`slug`, `path`, `research`, `grilled`, `done`, `total`, `next`, `landing`, `land`, `problems`, `steps`).

Ask questions by the global question rule (background first; ~/.claude/CLAUDE.md), recommended option first.

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
**Context**; decisions it yields go to their one home. There is no research without a plan: a single `/research`
call creates its research plan first (the research skill). When unsure whether a request is research or implementation, ask.

**A research plan never lands itself.** The user's workflow is research → an implementation plan → its landing:
`new --research` writes `Landing: manual`, so a finished research plan stops at its end (no `/mtm`, not into the
merge queue). Its research doc and decisions reach the default branch with the implementation plan that follows it
in the same worktree (that plan's `Landing: auto` lands both), or when the user runs `/mtm`. Never switch a research
plan to `auto`; only an implementation plan lands itself.

**Every implementation plan ends with its UATs.** Its last step before the landing (the template's "Write the
UATs") writes `plans/<NNNN>-<slug>/uat.md` (`plan.py uat` scaffolds it from `templates/uat.md`, typed `UAT`: its
`status` is the file's, `active` or `archived`, never a check's; a legacy uat.md keeps its header lines): the user acceptance
checks the user runs by hand on the default branch after the landing (`hal2-cli-plans uat next <plan>`, then `uat set
<plan> <check> pass|fail|skip|blocked`). Only what a human must see
goes there: derive the checks from the goal, each step's done-when and the diff (new panes, commands, keys, deep
links), drop what the plan's tests and your own verification already proved, keep what needs eyes and hands (layout,
feel, real data, other devices), riskiest first (`Priority: p1` = what the goal promises), at most about 10, each
with `Open:` (a hal2:// deep link) or `Run:` (a command) when one exists, steps and the expected result; tag checks
that should come back with later plans of the feature `regression`. Ids (`U1`, `U2`, ...) are never reused.
Never write a verdict into a checkout or commit one: `uat set` queues it in hal2's state root, and the next landing
from that machine appends it to the plan's committed `uat-results.jsonl` and regenerates `plans/uats.md` in its
candidate (hal2 plan 0214 step 12); a failed check becomes a shot in the plan's feature shotfile (the `shotfile`
key). A research plan has no UATs (`new --research` leaves the step out).

**The step table is the plan's state.** `/plan`, `/handoff` and the statusline all read it; nothing else tracks
progress. Update it the moment a step's check passes, never later.

**Parallel plans** (`new --parallel`) run independent steps at once, in subagents and in subservant sessions in
worktree slots 30-99 that never land: their table adds Needs, Touches and Who, and the lead runs them as in
[Run a parallel plan](#run-a-parallel-plan). A slot with `plans/LEAD` is such a subservant: it does one step only
([Work as a subservant](#work-as-a-subservant)).

**Good steps** fit one session (split a step that doesn't) and have a **Done when** that is a runnable command
where possible (`cargo test -p x`, `grep -rn "old" src | wc -l` = 0), otherwise one observable behaviour.
A done-when tests only what the step changed: the crates or packages it touched (`cargo nextest run -p <crate>`), or
a gate job for the branch's range (`gate/main.sh <job> --branch origin/main` in hal2). It never runs a whole-workspace
test (`--workspace`, a bare `cargo nextest run`) or a full gate job (a release bundle, an e2e stack) on the Mac: those
are the landing's CI; a check that needs one before then runs on the CI runner (hal2: `gh workflow run land.yml -f
ref=<branch> -f jobs=<job>`; hal2 plan 0157).

**Short and concise** (hal2's record plans-short-and-concise): one line per step, `plan.md` at most 150 lines, a
table cell at most 200 characters, a step file at most 120 lines; link the research, records and code instead of
repeating them; a question in `questions.md` is clear: plain words, what it is about, what each answer causes.

**A plan lands once, at its end.** `new` writes `landing: auto` into the plan's front matter (a legacy plan has a
`Landing: auto` line below the title; the JSON's `landing` is the same for both): when the plan's last step is done,
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

**The plan folder holds four records** (hal2's decision record
[record-formats](https://github.com/divramod/hal2/blob/main/.adr/record-formats.md); `new` writes all
four, each with a front matter envelope: `type`, `schema`, `title`, `description`, `status` and the type's keys):

| File | Holds | Written |
|---|---|---|
| `plan.md` | the overview: goal, context, the step table, Pre-authorized, Notes on the whole plan; `status` is `done` exactly when no step is open (`plan.py status` keeps it, `finished` and the other three files' `status`) | amended in place |
| `decisions.md` | the ledger of every decision taken while the plan is planned and run: `## D<n> · <date> · <user \| farmer \| lead \| agent> · <in-force \| promoted \| superseded \| ended <date>>`, then `**D:**` (one line), `**Words:**` (quoted; required unless `agent`), and where they apply `**Via:**`, `**Why:**`, `**From:** Q<n>`, `**Record:**` (a link to the decision record; exactly when `promoted`), `**By:** D<m>` (exactly when `superseded`) | appended, numbered on; only an entry's state and its Record and By lines ever change |
| `questions.md` | every question, the agent's and the user's, with its answer (the handoff skill's entries), plus `**Decision:** D<n>` when the answer is a decision | appended |
| `handoff.md` | the state a cleared session needs (Done, Next with its `Done when:`, Watch out, Start with); committed, so no PID, pane id, session name or absolute home path | overwritten by `/handoff` |

Beside them, **each step has its file** `steps/<n>.md` (hal2's shaped kind Step: `# Step <n>: <title>`, `## Task`,
then optional and in this order `## Needs and touches`, `## Approach`, `## Done when`, `## Your rules (a subservant)`,
`## Notes`, `## Result`; at most 120 lines): `plan.py status <n> next` writes it from `templates/step.md` when it is
missing (never over an existing one; a parallel plan's is its brief, `plan.py brief`), the grill adds its
`## Approach`, the step's end its `## Notes`. Status and who stay in the step table only.

A plan has no `## Decisions` section: an autogrill decision is a `D<n>` entry by `agent` with its **Why**, a user's
answer an entry with their quoted **Words**, and **Pre-authorized** names its entries by number. `python3 $S/plan.py
check` validates every plan folder with hal2's one records checker, `hal2-cli-records check --json` (keys, status
values, sections, entry headings, the links between questions, decisions and decision records, dead links, a status
against its step table) and prints one problem per line, each ending in its rule; run it after writing a ledger
entry, and `/handoff` and `/mtm` run it too. The checker is `$HAL2_CLI_RECORDS`, else `hal2-cli-records` on PATH;
without it the check is advisory: it prints `records unchecked: hal2-cli-records is not installed` and passes (the
plan numbers are still checked), and hal2's landing gate checks the records. `plan.py check <folder>...` checks the named
plan folders only, `plan.py scaffold` writes a ledger or handoff that is missing. A `plan.md` without front matter
is a **legacy plan** (every plan made before 2026-10-08; `format` in the JSON): it passes the check untouched, keeps
its `Landing:`, `Grilled:` and `Finished:` lines and its **Decisions** section, and is never migrated in passing.

**One home per decision** (the decision ladder): a question is an entry of `questions.md`; its answer, and every
other choice of the plan, an entry of `decisions.md`. A decision is **promoted** to a decision record (`.adr/`, the
`adr` skill) when a session that never reads this plan would have to know it to do its own work right: it binds
work outside the plan's steps, or after the plan has landed. Then the entry becomes `promoted` and links the record,
whose `origin` names the plan. Never promoted: the plan's order and who does what, a go or a stop, a base, a number
or a name reserved for the plan's branches. In a repository without decision records, what outlives the plan goes
to its intent doc (`INTENT.md` or equivalent); never into a generated decision log.

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
| `/plan start` | | the user's go: hand off, [switch](#model-and-effort-per-step) to the next step's model and effort in a fresh session, which runs the plan to its landing without a question |
| `/plan done [<step>]` | `/plan d [<step>]` | [finish a step](#finish-a-step) after its check passes |
| `/plan use <slug or number>` | `/plan u <ref>` | `python3 $S/plan.py use <ref>`, then Status |
| `/plan uat` | | `python3 $S/plan.py uat`: scaffold the current plan's `uat.md` (see above) |
| `/plan landing auto\|manual` | `/plan l a\|m` | `python3 $S/plan.py landing <auto\|manual>`: whether the current plan lands itself at its end |
| `/plan new --parallel <idea>` | `/plan p <idea>` | a parallel plan: the step table gets Needs, Touches and Who; it runs as in [Run a parallel plan](#run-a-parallel-plan) |
| `/plan ready` | | `python3 $S/plan.py ready --json`: the parallel plan's steps that can start now, and why the others wait |
| `/plan assign <n> <who>` | | `python3 $S/plan.py assign <n> <who>`: lead, subagent, user or `slot NN` (30-99) |
| `/plan brief <n>` | | `python3 $S/plan.py brief <n>`: scaffold the step's brief and print the subservant's first prompt |
| `/plan report <n>` | | `python3 $S/plan.py report <n>`: a subservant scaffolds its report ([Work as a subservant](#work-as-a-subservant)) |
| `/plan reports` | | `python3 $S/plan.py reports`: the subservants' reports arrived on their branches |
| `/plan new -g <title>` | `/plan r -g <topic>` | a global plan (see "Global plans" above; `--research` works too) |
| `/plan s -g <n>`, `/plan n -g <n>`, `/plan d -g <n> [<step>]` | | status, run, finish a step of global plan `<n>` |
| `/plan check` | `/plan c` | `python3 $S/plan.py check`: report plan numbers used twice and every problem of the plan folders' records |
| `/plan help` | `/plan h` | print this table and stop |

## New plan

1. Understand the idea: read `INTENT.md` (or the repo's decision record) and the code it touches. Settled
   decisions are not questions. Ask only what you can't find out.
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
4. Fill it in: **Context** links, 3–10 good **Steps** (see above; one line each, short and concise), first step
   `next` (`plan.py status 1 next` writes its `steps/1.md`), the rest empty. A research
   plan's steps end in its research doc (e.g. question and criteria, sources, compare, write `research.md`, record
   the decision). No step lands; steps checked after the landing come last ("after the landing: ..."). The plan
   lands itself at its end (`landing: auto`); when the user wants to land it themselves, `plan.py landing manual`.
   Write the front matter's `description` (one sentence, at most 200 characters: what the plan delivers; `new`
   takes the goal's first sentence) and record the decisions taken so far as entries of `decisions.md`.
5. **Autogrill it once** before offering it: run [`/grill auto`](../grill/SKILL.md#auto) on the plan (one round
   without questions: map the design tree, decide every open branch yourself by the repo's rules, record each
   decision in its home, adjust steps and checks), which stamps `plan.py grilled --auto`.
6. **User-only questions before implementation.** List every question only the user can answer: money, production
   deploys, accounts and secrets, paid resources, product choices. They are asked now, never mid-run: with the
   offer below (numbered, a recommended answer each), and the answers go into `decisions.md` (an entry by `user` with
   the quoted words) and the plan's **Pre-authorized** section names them (`D3: ...`; a legacy plan: the user's
   words and the date in the section) before step 1 runs. A plan nobody answers here (an autogenerated plan, a servant
   the farmer started) sends them to the farmer in one line each (SendMessage to the session in the repository's
   farmer slot `farmer-<repo>`; without one, `PushNotification`) and records them as open under **Pre-authorized**; the run starts
   with the steps that do not depend on them.
7. Show the plan and the round's decisions in a few lines, then end the reply with a plain-text question (never
   the question tool here: it would hide the plan), these three numbered options (plus the user-only questions):
   - **Run now** (recommended): [run it](#run-the-plan) from step 1; it runs to the end on its own and, with
     `Landing: auto`, lands;
   - **Another autogrill round**: `/grill auto` again (it looks for what is still open, deeper branches first),
     then this offer again;
   - **Manual grill**: `/grill` with question rounds (the autogrill's decisions are the recommended answers), then
     this offer again after its shared-understanding check.

   Stopping here is the user's free answer, not an option.

## Model and effort per step

Each step names the session's model and effort for it: the step table's `Model` (`haiku`, `sonnet`, `opus`,
`fable`, a full id) and `Effort` (`low` ... `max`) columns, empty for the plan's `run: <model> <effort>` (a legacy
plan: the line `Run: ...` below the title); `plan.py current` gives both per step and for `next`. The autogrill
picks them by the rubric: Opus high for design, new engines, the landing's code and big rewrites, xhigh for a
decision the plan turns on; Sonnet medium or high for well-specified work with a test as its check; Haiku only for
narrow mechanical work. A legacy table without the columns runs on the session's own model and effort.

- **The user's defaults never change** (the user, 2026-10-09: "new sessions should always set the effort level to
  medium and the model to opus 5.5"): a switch is for the running session only. Never type `/model` (Claude saves
  it as the default every new session starts on); hal2 restarts the session with process-only flags instead.
- **Between two steps with the same model and effort** the run goes on in the same session (the context check of
  [Finish a step](#finish-a-step) still hands off at its threshold).
- **Before a step whose model or effort differs** from the session's: `/handoff` (its Next is that step), then
  ```bash
  hal2-cli-agents switch --model <m> --effort <e> --prompt "/handoff c" --detach --json
  ```
  and end the turn with one line ("switching to <m> <e>, continuing with /handoff c"). hal2 waits for the turn's
  end, stops the session by signal and starts it again in the same pane with `claude --model <m> --effort <e>` and
  the prompt: a fresh session that continues the plan. When `switch` cannot start (no hal2, not in a pane), go on
  in this session and name it in the step's notes.
- **A step that fails its done-when twice** escalates once: effort one level up, else the next bigger model, through
  the same switch; record it in the step's notes.
- **`/plan start`** is the user's go for the current plan: no grill offer, no question; write the handoff, then the
  switch above with the next step's values (also when they equal the session's: the plan starts in a fresh
  context), and the fresh session runs the plan to its end and its landing.

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

- **a decision** nothing settles (the plan and its `decisions.md`, the decision records, the intent doc, the repo's
  rules for choosing between options): take the more professional, battle-tested option yourself and record it in
  its one home (an entry of `decisions.md` by `agent` with its **Why**; promoted to a decision record with the
  `adr` skill when it outlives the plan; a legacy plan: its **Decisions** section);
- **an outward-facing or irreversible action** (pushing, publishing, deleting data that is not the plan's own): do it
  when the plan's **Pre-authorized** section or a relayed go names it, else skip it and name it in the plan's final
  report; the landing of an auto plan at its end ([Land the plan](#land-the-plan)) is not one of these: the start of
  the plan agreed to it;
- **a user-only question** (money, a production deploy, an account or secret, a paid resource, a product choice): a
  step never stops to ask what **Pre-authorized** already answers. A go relayed by the farmer, a message whose first
  line is `farmer [<id>]: the user decided: "<the user's words>"`, is the user's own decision for what the quoted words say:
  act on it and record it under **Pre-authorized**. A new user-only question goes to the farmer in one line
  (SendMessage to its session; without one, `PushNotification`), and the run goes on with the steps that do not
  depend on it: **never wait idle for a go**. A cost found wrong mid-run within 2x of the authorized one (a price, a
  server size) is decided by you and recorded; beyond 2x it is a new user-only question;
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
   [New plan](#new-plan) step 7 (Run now, Another autogrill round, Manual grill). A grilled plan the user asked to run
   just starts. After the start nothing is asked any more (see above).

2. A parallel plan (`parallel` in the JSON) runs as [Run a parallel plan](#run-a-parallel-plan) says; in a
   subservant's slot (`lead` in the JSON) only its one step runs, as [Work as a subservant](#work-as-a-subservant)
   says. Otherwise, for each step, starting with the one marked `next`:
   0. Its `model` and `effort` differ from the session's (`plan.py current`'s `switch` is not null): switch first ([Model and effort per step](#model-and-effort-per-step)), with `switch`'s values.
   1. Detail it in its `steps/<n>.md` (written when it became next; `plan.py status <n> next` writes a missing
      one): the files it touches, the approach, the tests. Use subagents (with worktree
      isolation) for independent parallel parts.
   2. Implement it until its done-when check passes.
   3. [Finish the step](#finish-a-step): table, notes, commit, context check. Stop when the context check says so,
      otherwise go on with the next step.
3. When no step before the landing is left (`land` is `ready`, `manual` or `none`), the plan's end:
   - `ready`: [land the plan](#land-the-plan) now, in this run: no question, no context check, no handoff.
   - `manual`: say the plan is done and that the user's `/mtm` (or, for a research plan, the implementation plan
     after it) lands it; never start `/mtm` yourself and ask nothing.
   - `none` (a global plan): say it is done.

## Run a parallel plan

A big plan runs its independent steps at once: the **lead** (the session that runs the plan, in the plan's own
worktree) dispatches them to subagents and to **subservants**, agent sessions in worktree slots 30-99 that do one
step each, never land and report back. Everything below that is bookkeeping is code (`plan.py`, parallel.py); the
lead's model only judges (the brief's task, the merge, the review). Design: hal2 plan 0149's
`one-plan-answer.md`, sections D and G.

**The table** (`plan.py new --parallel` writes it): `| # | Step | Needs | Touches | Who | Done when | Status |`, the
plan's first table with `#`, `Step` and `Status`. A plan without the Needs column is sequential and works as above.

- **#**: integers, appended, never renumbered, so Needs stay valid when steps are added.
- **Step**: a short title; the full task lives in the step's brief `steps/<n>.md`, written when it becomes ready.
  Write a `|` inside a cell as `\|` (`plan.py` reads and writes it so; a row with too few cells is a clean error).
- **Needs**: the steps that must be done first, comma-separated ids and ranges (`1, 3-7`); blank or `-` is none.
- **Touches**: what the step changes, comma-separated: crates, packages and contracts (`rust:<crate>`,
  `ts:<package>`, `proto:<package>`, `docs`) and pseudo-resources a machine has once (`@hub-stack`, `@vault-test`,
  `@stripe-mock`, `@vm`, `@quiet-mac`, `@ci`, `@deploy`, `@land`). Two steps that share one never run at once. Each
  has room for one step, `@vm` for two; a `Capacity: @vm=3, @x=2` line under the title changes that. A row whose
  Step starts with `Milestone <n>` touches `@land`, so one land run goes at a time. Resources compare without
  backticks, spaces and case (`` `@VM` `` is `@vm`), the Capacity line's too.
- **Who**: `lead`, `subagent`, `user` (a batched physical action) or `slot NN` (a subservant, NN 30-99).
- **Status**: blank (open), `running`, `blocked <why>`, `done`; a step another plan absorbed is
  `done (absorbed into <NNNN> step <n>)`. A `blocked` step with a Who keeps its Touches and its slot like a running
  one.

`problems` names ids that are no integer or used twice, Needs no row has, bad Needs tokens and cycles; fix them
before dispatching.

**The commands** (the JSON of a parallel plan adds `parallel`, `running` and `ready`):

```bash
python3 $S/plan.py ready [--limit <n>] [--json]   # what can start now (open, Needs done, Touches free; greedy in table order); --json: why the others wait
python3 $S/plan.py assign <n> <who> [--force]     # set Who and `running`; refuses a step that is not ready and a taken slot; `slot NN` only 30-99
python3 $S/plan.py brief <n>                      # scaffold steps/<n>.md (templates/step-brief.md, never overwritten), print the subservant's first prompt
python3 $S/plan.py reports [--no-fetch]           # the running subservants' reports that arrived on origin/NN
python3 $S/plan.py watch [--interval 60]          # one line per newly arrived report: the lead's background Monitor
```

**Subagent or subservant.** A **subagent** takes a short step (about 30 minutes) that needs no build or test cycle
of its own (docs, briefs, research, plan text) or whose files are disjoint from everything running: it works in the
lead's tree, the lead runs its builds one at a time and commits its work. Give it worktree isolation only when the
repo's tracked `.claude/settings.json` sets `"worktree": {"baseRef": "head"}` (otherwise the isolated tree branches
from the default branch, not from the plan's work). A **subservant** takes everything else: any step with its own
build or test cycle, or longer than about 30 minutes. It runs in slot 30-99, never below (the user: "helper sessions
(subservants) only work in the worktrees 30+").

**The lead's loop** (the model wakes for judgment only):

1. `plan.py ready --json`. For each ready step up to the limits below: detail its brief (`plan.py brief <n>`, then
   fill in the task, files and approach in `steps/<n>.md`), commit and push the brief to `origin/<lead>`, then
   assign it:
   - a subagent: `plan.py assign <n> subagent`, then start it with the brief as its prompt;
   - a subservant: **reuse before create**: a slot 30+ whose last step is merged (and marked done) gets the next one:
     `plan.py assign <n> slot <NN>` rewrites its `plans/LEAD`, then its session is told to `git reset --hard
     origin/<lead>` and read the new brief, so its build cache stays warm; when the step's model or effort differs
     from that session's, `hal2-cli-agents switch <its pane> [--model <m>] [--effort <e>] --detach --prompt "<the
     prompt plan.py brief printed>"` restarts it at the step's values with the brief instead. Only when none is
     free start one first, at the step's model and effort, then assign the step to the slot create.py's JSON names
     (`"slot"`):
     ```bash
     python3 <create-worktree-session>/scripts/create.py --from 30 --base origin/<lead> \
       --lead "<lead-slot> <plan-slug> <n>" [--model <m>] [--effort <e>] --exact \
       --prompt "<the prompt plan.py brief printed>"
     python3 $S/plan.py assign <n> slot <NN>   # NN: the "slot" of create.py's JSON
     ```
     `assign` refuses a slot another running or blocked step holds, whose `plans/LEAD` names other work (another
     lead or plan, or a step not done) or where a farmer servant runs (a `running` entry of the farmer's
     `delegations.jsonl`); `--force` only after checking the slot by hand;
   - `lead` or `user`: `plan.py assign <n> lead|user`, then do it yourself, or batch it for the user (F of the
     design: physical actions only).
2. Run `plan.py watch` as a background Monitor; it prints a line when a subservant's report arrives on its branch.
3. For each report, one branch at a time: `git fetch`, `git merge --no-ff origin/NN`, resolve the shared files
   (below), regenerate what is generated (Cargo.lock, the workspace-hack, openapi.json), run the build check, the
   step's done-when and the gate jobs the merge touches (`hal2-cli-git changes --job` where hal2 runs the gates).
   Review the diff (a review subagent for a large one), take the report's lines for AGENTS.md and INTENT.md into
   them, push `origin/<lead>`, `plan.py status <n> done`, then dispatch again (point 1).
4. A subservant reports **blocked**: answer it from the plan and its decisions, or decide it and record it; a
   user-only question goes to the farmer like any other.
5. While a milestone lands, merge nothing: the candidate is fixed.

**Shared files are the lead's.** Only the lead writes `plan.md`, `INTENT.md`, `AGENTS.md`, lockfiles and generated
files (regenerated on merge), CI and gate config (`@ci`). A subservant puts the lines it wants there into its report.
Budgets and workspace member lists a subservant may append to; the lead resolves them on merge. A new protobuf
package in new files is free; a change to an existing package is `proto:<package>`, one step at a time.

**Milestones** land the plan's work in parts when the plan is too big to land once: a row "Milestone n: land ...",
whose Needs name what it carries, so the DAG covers it. Before asking to land, the lead runs every gate job the
candidate touches locally until it is green (a red landing holds the repository's merge queue). Then it asks the
farmer (or the user) for "land now"; a batch's pre-authorization may let it land after a silence it names. It lands
with `/mtm milestone` (the mtm skill's milestone mode: the queue is not kept, `CURRENT_PLAN` stays, no cleanup, so
the build cache stays warm), marks the row done, and the subservants merge `origin/<lead>` before they next report.
A milestone is a coherent set, about one or two days of work. Only the plan's last landing is the plan's own (`Land
the plan`).

**Limits**: subservants up to the farmer's `servant_limit` (by load) and only while the disk has room (a new slot
needs `create.py`'s `--min-free-gb`, 50 by default: a slot's Rust target is 10-30 GB); one step per `@` resource
(`@vm` two); one land run at a time. The farmer prunes a slot 30+ once its branch is in `origin/<lead>` and it
has been idle over an hour.

**The never-land guard** has three layers: code (hal2-git's queue refuses a slot with `plans/LEAD`; `plan.py`
refuses a subservant's writes to `plan.md`; the mtm skill's `subservant-guard.sh`), the farmer (it skips marked
slots: no "land now", no restart with `/mtm`, only with `/handoff c`; its `follow_up` never tracks a subservant, so
the lead watches and stops its own) and this prose.

**Hand-off.** The state is the step table, `steps/`, `reports/` and the lead's handoff (the plan's `handoff.md`; a
legacy plan: the root `HANDOFF.md`), which lists what is in
flight (step, who, since). The context check runs between merges instead of between steps; stop the `watch`
Monitor before a clear. After `/handoff c`: `plan.py current` and `ready --json`, `plan.py reports`, then the loop
again. The subservants keep working meanwhile; their reports wait on their branches.

## Work as a subservant

A slot with `plans/LEAD` (one line `<lead-slot> <plan-slug> <step>`, gitignored like `CURRENT_PLAN`, which names
the lead's plan so the statusline and autoclear work) runs **one step of the lead's plan and nothing else**.
`plan.py current` shows it as `lead`. Its brief `plans/<plan>/steps/<step>.md` holds the task and these rules:

1. **Start**: `git fetch origin`; when the slot's branch is already in `origin/<lead>` (a reused slot),
   `git reset --hard origin/<lead>`, else `git merge origin/<lead>`. Never run `/mfm` (the lead's branch is the
   base, not the default branch).
2. **Only this step**: commit as you go, each message ending `(plan <NNNN> step <n>)`. Never edit `plan.md` (hal2
   would show the subservant's copy; `plan.py` refuses `new`, `status`, `assign`, `grilled`, `landing`, `uat` and
   `brief` here), the briefs or another step's report; never run another step, even when it is ready.
3. **Before reporting**: merge `origin/<lead>` again, run the step's done-when and the gate jobs the change touches
   until green.
4. **Report**: `plan.py report <step>` scaffolds `plans/<plan>/reports/<step>.md` (`templates/report.md`): what
   changed, the checks and their results, the lines for the lead's shared files, follow-ups. Commit it,
   `git push -u origin HEAD`, then one line to the session `ListAgents` shows in the lead's slot (look it up by slot:
   names change after a clear): `step <n> reported: <one line>`.
5. **Never land**: no `/mtm`, no merge queue, no push to the default branch; the lead merges the branch.
6. **Blocked**: one line to the lead's session, then wait for its answer; never ask the user.
7. **After a clear**: `/handoff c` continues this one step only, never the plan and never a landing. The context
   check and the hand-off work as in [Finish a step](#finish-a-step), without the table update.

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
3. Record what the step taught under `## Notes` of its `steps/<n>.md` (its commit, what was decided while
   building, the checks' results; `## Result` when the step produced something to hand on), and adjust later steps
   when reality changed them (say what and why; decisions go to their one home). The plan's own **Notes** keep only
   what concerns the whole plan.
4. **Commit the step**: one commit with the step's changes, its `steps/<n>.md` and the updated plan, message
   `<type>(<scope>): <what> (plan <NNNN> step <n>)`. Stage only the files this step changed (other uncommitted
   work in the tree stays as it was). Never push without the user's consent.
5. **Check the context window** before starting the next step:
   ```bash
   python3 $S/context.py            # threshold: hal2's agents.toml [autoclear] step_tokens (a step boundary clears earlier than the guard's ceiling), else its ceiling (tokens/percent), else 35; percent as the statusline shows it
   ```
   - No step is left that you run now (this was the last step, or only steps checked after the landing remain) and
     nothing is left to do after it (a `manual` plan that waits for the user's `/mtm`, a plan that has landed): skip
     the check and never hand off or clear there: its report stays on screen.
   - `stop` is false: continue with the next step, or with the plan's end ("Run the plan" point 3).
   - `stop` is true: stop the plan here and hand off. Also before an auto plan's landing (hal2 plan 0181: hal2's
     guard stops the `/mtm` that would start a landing above the threshold): the handoff's Next is then `/mtm` (the
     plan's own landing, "Land the plan"), and the continued session lands with a fresh context.
     1. Stop your background work (TaskStop every background shell, subagent, workflow and monitor you started):
        after a clear their notifications would wake the fresh session. Note in the handoff what was stopped and
        must be rerun. **Never a landing or a waiting reserve** (`hal2-cli-git worktree merge-to-main|reserve`): it
        goes on across the clear; name it in the handoff (the command, the slot, its ticket's state) instead.
     2. Run `/handoff` (it records decisions, writes the plan's `handoff.md` (a legacy plan: the root `HANDOFF.md`)
        with the plan's next step and commits them).
     3. `autoclear` is true: start the automatic clear-and-continue, then end your turn with one line saying the
        session clears and continues with `/handoff c`; do nothing after it (the clear waits for your turn to end,
        waits out a draft the user types, and never types into a non-empty prompt):
        ```bash
        hal2-cli-agents clear-and-continue --detach --json    # pane from $TMUX_PANE or $HAL2_TERMINAL, session from $CLAUDE_CODE_SESSION_ID
        ```
        `already-running` is fine: hal2's guard already started the job (it stops a session above the threshold at
        its next tool, hal2's [research 0010](https://github.com/divramod/hal2/blob/main/research/0010-autoclear-watcher/research.md)): just end your turn. When it fails to start otherwise (autoclear
        disabled, ...), say so and fall back to the next point.
     A tool denied with "hal2: context at N% ... run /handoff now" is that guard: stop the step where it is, do
     points 1-2 (only the hand-off's tools run now; name in the handoff what was cut off), then end your turn: the
     job is already waiting, so skip point 3.
     4. `autoclear` is false (its `autoclear_reason` says why: disabled, not Claude Code, neither in tmux nor a hal2 terminal, no hal2):
        tell the user to run `/clear` and then `/handoff c` to continue.
   - `known` is false (not Claude Code, no transcript): judge the fill level yourself and say so; when in doubt,
     stop and hand off as above.

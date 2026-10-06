# Plan 0013: parallel plans

Grilled: 2026-10-06 (autogrill ×1)

Landing: auto

Created 2026-10-06. `plans/CURRENT_PLAN` names the active plan; helper files for this plan live next to this file.

## Goal

A plan's steps run in parallel: the step table gets Needs, Touches and Who; `plan.py` schedules the ready steps and
writes their briefs; the lead dispatches subagents and subservants (worktree slots 30+) that never land and report
back; create-worktree-session, mtm, handoff and the farmer know the `plans/LEAD` marker. Sequential plans work as
today.

## Context

- The farmer's brief: `~/.hal/git/worktree/hal2/farmer-hal2/roles/farmer/briefs/2026-10-06-parallel-plans.md`
  (runtime state, never committed), the user's words of 2026-10-06 quoted there.
- The design, agreed by the farmer and hal2's 02 and approved by the user: hal2 02's
  `plans/0145-app-electron-desktop-1-refactore-repositories-to-projects-sw/one-plan-answer.md` (on `origin/02`),
  sections **D** (parallel plans 1-12), **G** (slots 30+) and **(3)** (this plan's scope).
- [.adr/deterministic-first.md](../../.adr/deterministic-first.md): the lead's loop is code, the model only judges.
- Code: [plan.py](../../skills/plan/scripts/plan.py), [create.py](../../skills/create-worktree-session/scripts/create.py),
  [mtm SKILL.md](../../skills/mtm/SKILL.md), [decisions.py](../../skills/handoff/scripts/decisions.py), the farmer's
  [mtm_scan.py](../../skills/farmer/scripts/mtm_scan.py), [boss.py](../../skills/farmer/scripts/boss.py),
  [lead_scan.py](../../skills/farmer/scripts/lead_scan.py), [duties.py](../../skills/farmer/scripts/duties.py),
  [prune.py](../../skills/farmer/scripts/prune.py), [delegation.py](../../skills/farmer/scripts/delegation.py).

## Steps

Each step is detailed when it is next; keep one line per step here. The plan lands once, after all its steps
(`Landing: auto`: the plan skill runs `/mtm` then); steps checked only after the landing come last, their done-when
starting "after the landing: ...".

| # | Step | Done when | Status |
|---|---|---|---|
| 1 | plan.py parallel table: `split_row` honours `\|` (and writes it back escaped) with a clean error on short rows; Needs, Touches, Who read; `new --parallel`; problems for bad ids, unknown Needs and cycles; `ready [--json]`, `assign <n> <who>`; `current` lists running and ready; writes refused in a slot with `plans/LEAD` | `python3 -m unittest discover -s skills/plan/scripts` green, the new tests among them, the old ones unchanged | next |
| 2 | plan.py `brief <n>` (templates/step-brief.md, with the subservant's exact first prompt), `report <n>` (templates/report.md) and `reports [--json]` / `watch` (the lead's Monitor: reports arrived on origin/NN) | the same unittest run green with tests for brief, report, reports | |
| 3 | plan SKILL.md: the parallel table, "Run a parallel plan" (the lead's loop as code, subagent vs subservant, a subservant's life, shared files, milestones, limits, hand-off), the subservant's rules; the help table | `grep -c "Run a parallel plan" skills/plan/SKILL.md` ≥ 2 and every D 1-12 point has its paragraph (checked against the design) | |
| 4 | create-worktree-session: `--from <NN>`, `--base <rev>` (`git branch -f NN <rev>`, a reused clean slot reset), `--lead "<slot> <plan> <step>"` writes `plans/LEAD` and `CURRENT_PLAN` (ignored through info/exclude when the repo does not ignore it), free disk checked before a new slot, `--exact` documented | `python3 -m unittest discover -s skills/create-worktree-session/scripts` green with tests for each flag | |
| 5 | mtm: `scripts/subservant-guard.sh` refuses in a slot with `plans/LEAD` (bats test), SKILL.md runs it first; milestone mode (`/mtm milestone`: no `--keep-reserved`, CURRENT_PLAN kept, no /cleanup) | `bats skills/mtm/scripts` green | |
| 6 | handoff: decisions.py reports the `plans/LEAD` marker (`lead` in JSON, a line in the text); SKILL.md: `/handoff c` in a marked slot continues that one step only | `python3 -m unittest discover -s skills/handoff/scripts` green with the marker test | |
| 7 | farmer skips marked slots: mtm_scan (no work-not-queued, the marker in each worktree), boss (no /mtm text to a marked slot, a holder wakes the farmer), lead_scan and duties.plan_lead (a stop mid-step gets "continue your step", never "land"), instructions/mtm.md and lead.md | `cd skills/farmer/scripts && python3 -m unittest` green with the new tests | |
| 8 | farmer prune and delegation: a marked 30+ slot is removed once origin/NN and HEAD are in origin/<lead> and it has been idle over an hour (origin/NN deleted then); the farmer's own servants start in 30+ (`--from 30`, free sessions from 30 only); SKILL.md and reference.md | the same farmer test run green with tests for the prune rule and the delegation's slots | |
| 9 | Write the UATs: `uat.md` beside this file (`plan.py uat`), only the checks a human must do on the default branch after the landing | `plan.py current` shows `uat` with its checks; `python3 scripts/check-plugins.py` ok; every scripts folder's tests green | |
| 10 | hal2's 02 reviews the diff: a summary to the session in hal2 slot 02, its findings fixed, its okay recorded under Decisions | the okay quoted under Decisions | |

## Pre-authorized

User-only decisions (money, production deploys, accounts and secrets, paid resources, product choices), asked and
answered before implementation, with the user's words and the date; the run acts on them without asking again.

- 2026-10-06 (the user, through the farmer's brief): the parallel-plans design of 02's one-plan-answer.md D, G and
  (3). User: "steps, which can be done in parallel will be done in parallel in subagents or subservants",
  "helper sessions (subservants) only work in the worktrees 30+", "i do not have to interact with 02 after the plan
  is going into the stage of implementation".
- Landing on the skills repo's main after 02's okay (the farmer's role file: "It lands on the skills repo's main
  with /mtm at its end"). No other outward-facing action: the plan needs no further user-only decision.

## Decisions

- 2026-10-06 (servant, by the design): the tracked `hal2/.claude/settings.json` (`worktree.baseRef = head`) is not
  this plan's work (the farmer: a question to the user). hal2's own code (the guard in hal2-git) is 02's lead step.
- 2026-10-06 (autogrill 1) **Parallel or not**: a step table with a `Needs` column is a parallel plan; without it
  every command behaves as today. Statuses: starting with `done`, `running` or `blocked`; anything else (blank,
  `next`) is open.
- 2026-10-06 (autogrill 1) **Needs** are comma-separated integer ids and ranges (`3-7`); blank or `-` is none. A
  parallel plan's `problems` name a non-integer or repeated id, a Needs id no row has, and a cycle.
- 2026-10-06 (autogrill 1) **Touches** are comma-separated tokens; two steps conflict when they share one. Every
  resource has room for one step, `@vm` for two (D 2); a `Capacity: @vm=2, @x=3` line under the title overrides. A
  row whose Step starts with `Milestone <n>` touches `@land` too.
- 2026-10-06 (autogrill 1) **`ready`** picks greedily in table order: open, not after-landing, every Need done, its
  Touches free of the running steps' and of those picked before it; `--limit <n>` caps it. JSON: `ready` and
  `waiting` (each open step with why it waits).
- 2026-10-06 (autogrill 1) **`assign <n> <who>`**: who is `lead`, `subagent`, `user` or `slot NN` with NN 30-99
  (G); a step that is not ready is refused unless `--force`; it sets Who and `running`. For `slot NN` whose
  worktree already sits beside the lead's checkout (reuse, G) it also rewrites that slot's `plans/LEAD` and
  `CURRENT_PLAN`.
- 2026-10-06 (autogrill 1) **The marker** `plans/LEAD` is one line `<lead-slot> <plan-slug> <step>` (the slug, so it
  matches CURRENT_PLAN), gitignored per worktree like CURRENT_PLAN; where the repo does not ignore it, create.py adds
  it to the clone's `info/exclude` (hal2's `.gitignore` is 02's side).
- 2026-10-06 (autogrill 1) **A subservant never edits plan.md, as code**: in a slot with `plans/LEAD`, plan.py
  refuses `new`, `status`, `assign`, `grilled`, `landing`, `uat` and `brief`; `current`, `list`, `use`, `ready`,
  `report`, `reports` and `check` work.
- 2026-10-06 (autogrill 1) **Briefs and reports**: `brief <n>` writes `steps/<n>.md` from `templates/step-brief.md`
  (never overwriting) and prints the subservant's exact first prompt; `report <n>` scaffolds `reports/<n>.md` from
  `templates/report.md`; `reports` fetches each running `slot NN` step's branch and lists the reports arrived on
  `origin/NN`; `watch [--interval s]` prints one line per newly arrived report (the lead's Monitor, D 5).
- 2026-10-06 (autogrill 1) **create.py**: `--from NN` (1-99) starts the slot search there; `--base <rev>` fetches
  origin when the rev is `origin/...`, then `git branch -f NN <rev>` for a new slot or `reset --hard <rev>` for a
  reused clean one, and skips a slot whose leftover branch NN holds commits neither in the rev nor on origin's
  default branch; `--lead "<slot> <plan> <step>"` writes the marker and CURRENT_PLAN (before the start in an
  existing worktree, right after `worktree run` created a new one); a new worktree needs `--min-free-gb` free disk
  (default 50: a slot's Rust target is 10-30 GB).
- 2026-10-06 (autogrill 1) **mtm**: `scripts/subservant-guard.sh` exits 1 naming the lead in a marked slot, 0
  silently elsewhere; mtm runs it before step 1. Milestone mode is `/mtm milestone`, run only by a lead for a
  milestone row: no `--keep-reserved`, CURRENT_PLAN kept, no after-landing cleanup, no plan finish beyond the
  milestone row.
- 2026-10-06 (autogrill 1) **handoff**: decisions.py adds `lead` (`slot`, `plan`, `step`) to its JSON and a `lead:`
  line to its text; `/handoff c` there continues that step only (never the plan, never a landing).
- 2026-10-06 (autogrill 1) **farmer**: every worktree in mtm_scan carries `lead`; a marked slot gets no
  `work-not-queued`; a marked orphan is restarted only with `/handoff c` (never `/mtm`), else the farmer is woken; a
  marked slot holding the queue wakes the farmer (`subservant-holds`), never gets the /mtm text; plan_lead tells a
  marked slot stopped mid-step to continue its step, never to land.
- 2026-10-06 (autogrill 1) **prune of 30+**: a marked slot 30-99 is free when HEAD, origin/NN and every side branch
  `NN-*` are in `origin/<lead>`, nothing is uncommitted, no ticket or busy agent, no session active in the last hour
  and no build runs; `remove` fetches and checks again, removes with `--force` (its branch is not on main by
  design) and deletes `origin/NN` once it is in `origin/<lead>`. A marked slot below 30 is never pruned.
- 2026-10-06 (autogrill 1) **The farmer's servants**: delegation reuses only free sessions in slots 30+ and creates
  with `--from 30`; follow_up stays on the farmer's own ledger, so a subservant (not in it) is never followed up.

## Notes

- <anything learned along the way that changes the plan>

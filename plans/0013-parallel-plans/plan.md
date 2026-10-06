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
  `plans/0149-hal9k-the-whole-roadmap-in-one-plan/one-plan-answer.md` (on `origin/02`; first written under plan 0145),
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
| 1 | plan.py parallel table: `split_row` honours `\|` (and writes it back escaped) with a clean error on short rows; Needs, Touches, Who read; `new --parallel`; problems for bad ids, unknown Needs and cycles; `ready [--json]`, `assign <n> <who>`; `current` lists running and ready; writes refused in a slot with `plans/LEAD` | `python3 -m unittest discover -s skills/plan/scripts` green, the new tests among them, the old ones unchanged | done |
| 2 | plan.py `brief <n>` (templates/step-brief.md, with the subservant's exact first prompt), `report <n>` (templates/report.md) and `reports [--json]` / `watch` (the lead's Monitor: reports arrived on origin/NN) | the same unittest run green with tests for brief, report, reports | done |
| 3 | plan SKILL.md: the parallel table, "Run a parallel plan" (the lead's loop as code, subagent vs subservant, a subservant's life, shared files, milestones, limits, hand-off), the subservant's rules; the help table | `grep -c "Run a parallel plan" skills/plan/SKILL.md` ≥ 2 and every D 1-12 point has its paragraph (checked against the design) | done |
| 4 | create-worktree-session: `--from <NN>`, `--base <rev>` (`git branch -f NN <rev>`, a reused clean slot reset), `--lead "<slot> <plan> <step>"` writes `plans/LEAD` and `CURRENT_PLAN` (ignored through info/exclude when the repo does not ignore it), free disk checked before a new slot, `--exact` documented | `python3 -m unittest discover -s skills/create-worktree-session/scripts` green with tests for each flag | done |
| 5 | mtm: `scripts/subservant-guard.sh` refuses in a slot with `plans/LEAD` (bats test), SKILL.md runs it first; milestone mode (`/mtm milestone`: no `--keep-reserved`, CURRENT_PLAN kept, no /cleanup) | `bats skills/mtm/scripts` green | done |
| 6 | handoff: decisions.py reports the `plans/LEAD` marker (`lead` in JSON, a line in the text); SKILL.md: `/handoff c` in a marked slot continues that one step only | `python3 -m unittest discover -s skills/handoff/scripts` green with the marker test | done |
| 7 | farmer skips marked slots: mtm_scan (no work-not-queued, the marker in each worktree), boss (no /mtm text to a marked slot, a holder wakes the farmer), lead_scan and duties.plan_lead (a stop mid-step gets "continue your step", never "land"), instructions/mtm.md and lead.md | `cd skills/farmer/scripts && python3 -m unittest` green with the new tests | done |
| 8 | farmer prune and delegation: a marked 30+ slot is removed once origin/NN and HEAD are in origin/<lead> and it has been idle over an hour (origin/NN deleted then); the farmer's own servants start in 30+ (`--from 30`, free sessions from 30 only); SKILL.md and reference.md | the same farmer test run green with tests for the prune rule and the delegation's slots | done |
| 9 | Write the UATs: `uat.md` beside this file (`plan.py uat`), only the checks a human must do on the default branch after the landing | `plan.py current` shows `uat` with its checks; `python3 scripts/check-plugins.py` ok; every scripts folder's tests green | done |
| 10 | hal2's 02 reviews the diff: a summary to the session in hal2 slot 02, its findings fixed, its okay recorded under Decisions | the okay quoted under Decisions | next |

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
  existing worktree; a new one create.py adds itself before the start, see step 10's decision); a new worktree needs `--min-free-gb` free disk
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
- 2026-10-06 (servant, step 4) `create.py --lead` implies `--exact`: a subservant's first prompt never runs `/mfm`
  (it would merge the default branch into a branch based on the lead's).
- 2026-10-06 (servant, step 5) milestone mode skips mtm's step 5 entirely instead of finishing the milestone row
  there: the queue is released at step 4, so a row commit would need a second landing; the lead marks the row done
  in its own branch and the next landing carries it.
- 2026-10-06 (servant, step 7) every queue ticket of a marked slot (waiting ones too) is `subservant-holds` only,
  never a head-of-queue, `waiter-gone` or `long-queue` finding; the boss turns any landing finding for a marked slot
  into that wake; a marked orphan is restarted with `/handoff c` on the marker alone (HANDOFF.md still needed); only
  a marked stop that announces its next step gets "continue your step", a waiting one wakes the farmer.
- 2026-10-06 (servant, step 8) prune's idle signal for a marked slot is the agent's `since` and the mtime of
  `plans/LEAD` (a reused slot is fresh); a broken marker or a missing `origin/<lead>` refuses the prune; a marked
  slot below 10 is not cleaned either; `remove` runs `worktree remove NN --force`, then deletes `origin/NN` after one
  more ancestry check. `delegation.start` read a `pane` field `free.py` never prints (it prints `panes`): fixed.
- 2026-10-06 (hal2's 02, step 10 review 1): "findings, not okay yet": 1 HIGH /mtm milestone through CI left the
  queue reserved; 2 the guard checked `.` for `/mtm <slot>`; 3 the farmer restarts merged subservants (ahead
  counted against main, not origin/<lead>); 4 `assign` reassigns a running slot or a farmer servant's slot, and
  SKILL.md runs assign before create.py; 5 a blocked step frees its Touches; 6 create.py marks a new slot after the
  agent started; 7 Touches compared verbatim; 8 an f-string with nested quotes (Python 3.10/3.11); 9 the brief's
  commit suffix `(plan {slug} ...)`, not NNNN; 10 a malformed marker counts as unmarked in mtm_scan and
  decisions.py; 11 merge trains take marked slots; 12 finished idle subservants wake the farmer hourly; 13
  `plan.py --root <lead>` from a marked slot edits the lead's plan. 14: milestone rows' done-whens start "landed:",
  no change. 1-6 must be fixed, 7-13 as I see fit: all 13 get fixed. 1-2 fixed in `ebcb0f6`.
- 2026-10-06 (servant, step 10, finding 6) `worktree run --detach` returns before the terminal host creates the
  worktree and hal2 has no create-without-start for a chosen slot, so for `--lead` create.py adds the worktree
  itself (`git worktree add` on branch NN, a best-effort `git push -u origin NN`, `hal2-cli-secrets reveal` when
  `.secrets/` exists), writes the marker, then runs `worktree run` on it; a bad `--lead` is refused before any slot
  is picked. Plain sessions still let hal2 create the worktree.
- 2026-10-06 (the user, via the farmer's instruction skills/30-1): before landing, mtm's CI landing waits until no
  `land.yml` run is unfinished (`gh run list --workflow land.yml --limit 10 --json databaseId,headBranch,status --jq
  '.[] | select(.status != "completed")'`, queued runs too) before taking the queue and before every candidate push;
  `skills/mtm/scripts/land-runs.sh`, references/ci.md's Land. User: "the mtm skill should have a mention of the
  command on how to check in the gh workflow list, if he can start now or needs to wait".
- 2026-10-06 (servant, step 10, findings 3, 10-12) `skills/farmer/scripts/lead_marker.py` reads `plans/LEAD` for
  mtm_scan, lead_scan, trains and prune; a broken marker is `{bad: true}` and keeps the slot marked everywhere (no
  /mtm, no `/handoff c`, a wake; decisions.py prints `lead: broken marker`). A marked slot is restarted only when
  `origin/<lead>` lacks some of its work (`missing`). An idle subservant stops waking the farmer once its report is
  on `origin/NN`, or HEAD is in `origin/<lead>` and holds the report: HEAD in `origin/<lead>` alone is also true of a
  freshly created subservant.
- 2026-10-06 (hal2's 02, step 10 review 2): "all 13 earlier findings are fixed"; four new: 1 MED land-runs.sh before
  an exit-6 rerun blocks it past the 10-min park grace; 2 LOW a queue wait goes stale before the push; 3 LOW no time
  limit; 4 LOW the guard resolves only folder names (`main`, named slots, "2" matched "02").
- 2026-10-06 (servant, step 10 review 2) a CI landing reserves first (`worktree reserve`, which merge-to-main takes
  over), then `land-runs.sh`, then `merge-to-main`; again only before a rerun after exit 3 or 4 (held already: no
  reserve), never before an exit-6 rerun. `land-runs.sh --max-wait <min>` (default 60) exits 7: tell the farmer.
  The guard resolves `<slot>` through `hal2-cli-git worktree list --json`, else by folder name compared as text
  (`main`: the main checkout).

## Notes

- 2026-10-06 step 1: the parallel logic lives in `skills/plan/scripts/parallel.py` (plan.py would pass 750 lines);
  plan.py wires it (`split_row`/`join_row` with `\|`, `set_cells`, `describe_safe` for `list`, `parallel_table` for
  `new --parallel`, `refuse_subservant`, `run_parallel`, `watch`). Steps 1 and 2's code and both templates
  (`templates/step-brief.md`, `templates/report.md`) are in the WIP commit `74e09f1`; their tests
  (`skills/plan/scripts/test_parallel.py`) are not written yet: the context guard cut the write off.
- 2026-10-06 step 3: the design moved with hal2 02's commit `d940287d` to plan 0149's folder; SKILL.md cites it there.
  "Run a parallel plan" and "Work as a subservant" cover D 1-12 and G; create.py's `--from`, `--base`, `--lead` and
  `--min-free-gb` are documented there ahead of step 4, which implements them.

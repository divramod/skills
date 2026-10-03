# Plan 0007: owner: everything deterministic runs as code

Grilled: 2026-10-03 (autogrill ×1)

Landing: auto

Created 2026-10-03. `plans/CURRENT_PLAN` names the active plan; helper files for this plan live next to this file.

## Goal

The owner costs tokens only for judgment: an external deterministic tick runs every opted-in duty and task, does every rule-based action itself, and wakes the owner's Claude session only with the items that need judgment, with just the instructions they need.

## Context

- [analysis.md](analysis.md): every owner step classified as D (deterministic), T (templated) or J (judgment), the cost
  today (~25k tokens per round, quiet or not) and the design
- [.adr/deterministic-first.md](../../.adr/deterministic-first.md): the rule this plan applies
- The owner skill: `skills/owner/` (SKILL.md, subskills, scripts `mtm_scan.py`, `lead_scan.py`, `ci_scan.py`,
  `due.py`); sanity-watch's `scan.py`, fix-autoclear's `evidence.py`, create-worktree-session's `create.py`,
  list-free-worktrees' `free.py`, delete-worktree-session's `stop.py`
- hal2: `hal2-cli-agents send|list`, `hal2-cli-git worktree ...`, the owner slot `~/.hal/git/worktree/hal2/owner`
  with OWNER-ROLE.md on branch `owner`; the owner's state `~/skills/owner/hal2/`

## Steps

Each step is detailed when it is next; keep one line per step here. The plan lands once, after all its steps
(`Landing: auto`: the plan skill runs `/mtm` then); steps checked only after the landing come last, their done-when
starting "after the landing: ...".

| # | Step | Done when | Status |
|---|---|---|---|
| 1 | `owner.py` skeleton: `start-check` and `tick` running the round frame (stay current, the OWNER-ROLE.md edit, due, a log line per action, the summary from the log), plus `--dry-run` | `python3 skills/owner/scripts/owner.py tick --dry-run` in the owner slot prints the due items and the planned actions; unit tests pass | done |
| 2 | The D/T actions of merge-to-main-boss in `tick` (priority front, wake → release rule, waiter-gone, load-high pause/go, flaky ledger, work-without-agent with HANDOFF), messages through `hal2-cli-agents send` to idle sessions only | tests per action on fixtures; a dry run on the live queue names the right actions | done |
| 3 | The D/T actions of development-lead, ci (transient-rerun regex, runners, hung runs, slot-red), watch (sanity-watch `scan.py resume`), autoclear (known continuations) | tests per action; dry runs on live data | done |
| 4 | Delegation as code: `owner.py delegate --brief`, briefs from templates, limit, free/new slot, prompt, log; `follow-up` (landed → stop idle worker) | a fixture test spawns nothing but prints the exact create.py/free.py calls; a live dry run names them (the first live delegation: step 9) | done |
| 5 | OWNER-ROLE.md tasks with machine-readable Check/Act (a command in backticks runs; `notify`, `delegate`, prose = wake); hal2's four tasks converted as a proposal for the user ([owner-role-hal2-tasks.md](owner-role-hal2-tasks.md)) | `due.py check` names each task's mode; tick runs hal2's proposed tasks with no wake (live checks) | done |
| 6 | `needs_model` + wake: tick writes `~/skills/owner/<repo>/wake.json` (items, evidence, instruction paths) and wakes the owner session (`hal2-cli-agents send <pane> "/owner act"`) only when it is non-empty; `/owner act` reads only that | a quiet tick adds no turn to the owner's transcript; an injected J item wakes it once | next |
| 7 | External timer: `owner.py install-timer` (launchd on macOS, systemd user timer on Linux) at `loop_cron`; `/owner start` installs it, `/owner stop` removes it; Claude cron no longer used | `launchctl list` names the owner's timer; ticks appear in the log every interval with the session idle | |
| 8 | Skill text split: SKILL.md down to start/stop/act/authority, `instructions/<kind>.md` per J kind, subskills only for the woken parts; README and description updated | SKILL.md under 8 KB; every J kind has its instruction file; check-plugins passes | |
| 9 | Measure: one hour of ticks on hal2, model tokens of the owner session before vs after | the owner's transcript shows ≤ 1 wake per real J item; noted in the plan | |
| 10 | Write the UATs: `uat.md` beside this file (`plan.py uat`), only the checks a human must do on the default branch after the landing | `plan.py current` shows `uat` with its checks | |

## Decisions

- 2026-10-03 (user): everything that can be done deterministically is done deterministically
  ([.adr/deterministic-first.md](../../.adr/deterministic-first.md)); the goal is to save tokens.
- 2026-10-03 (planning): the owner's loop moves from Claude's cron to an external timer so a quiet round costs no model
  call; the Claude session is woken only for judgment items.
- 2026-10-03 (planning): templated messages go through `hal2-cli-agents send` (idle sessions only), the model's
  SendMessage only for judgment answers inside a wake.
- 2026-10-03 (autogrill 1): the tick separates planning from doing: every duty produces planned actions as data
  (`{duty, kind, slot, do: send|run|record|wake|notify, text|argv}`), an executor carries them out; `--dry-run` only
  plans and prints, so it touches nothing (no fetch, no commit, no `due.py ran`, no log, no send).
- 2026-10-03 (autogrill 1): code in `skills/owner/scripts/`, stdlib only, importing `due.py` and `mtm_scan.py` as
  modules; files stay under 300 code lines (`owner.py` the CLI, `tick.py` the round frame, one module per duty's
  actions from step 2 on).
- 2026-10-03 (autogrill 1): "stay current" is `hal2-cli-git worktree merge-from-main --json` in the owner slot (the
  fetch, merge, setup tasks and hook /mfm runs); exit 3/4 becomes a J item `mfm-failed` and the round goes on with the
  slot as it is.
- 2026-10-03 (autogrill 1): the tick and the Claude cron loop never run together: `~/skills/owner/<repo>/mode` says
  `claude` (missing = claude) or `timer`; a tick without `--dry-run` refuses (exit 4) unless the mode is `timer`.
  Step 7's `install-timer` writes `timer`, its removal `claude`. A `tick.lock` flock makes overlapping ticks exit 0
  with `busy`.
- 2026-10-03 (autogrill 1): tick actions log through `mtm_scan.log` with `"by": "tick"`; the per-round summary file
  is written only when the round logged an action or has findings, `latest.md` every round (step 8 updates the
  skill's "quiet round" text).
- 2026-10-03 (autogrill 1): the tick has no notification channel of its own: notices (an invalid OWNER-ROLE.md, a
  redeploy) are `notify` items in the wake file and the woken session pushes them batched (step 6); until step 6 the
  tick prints them.
- 2026-10-03 (autogrill 1): exit codes of `owner.py`: 0 ok, 1 OWNER-ROLE.md invalid, 2 a tool missing, 3 no
  OWNER-ROLE.md, 4 not the owner slot, a dirty slot or not in timer mode.
- 2026-10-03 (autogrill 1): no landing step: the plan runs in the skills repo's main checkout (shared with another
  session), so each step is committed with its files only and pushed (the user's standing go for the skills); the
  plan skill's landing finds nothing to land and says so.
- 2026-10-03 (step 2): a templated message is typed only into a resting session (`idle|done|sleeping`) whose
  prompt box is empty (`deliver.py`, the rule of hal2-agents' `scrape::claude_input`, ported); otherwise it becomes a
  `relay` that the woken session sends verbatim with SendMessage (Claude Code queues it for a busy session).
  Proposal for hal2: `hal2-cli-agents send --if-empty`, so the rule lives once.
- 2026-10-03 (step 2): a slot with an open `ask` in the owner's log (no `answered` after it) gets no message, wake
  or new session from the tick (the live owner held slot 11's benchmarks for the user's go).
- 2026-10-03 (step 3): dedupe and the waiting-for-user rule live once, in `tick.fresh` (an action's `key` +
  `window`, companions `after` a key); planners only plan. Kinds that stay J for now, being rare and needing a look
  at a host or a log: ci `queued-long`/`running-long`, watch `restore` (F8 orphans can be days old) and `judge`, the
  boss's `active-long`.
- 2026-10-03 (step 4): step 4's live delegation moves to step 9: the owner's Claude loop still runs (mode `claude`)
  and delegates the same findings, so a delegation from outside it now would double a worker. Step 9 switches hal2's
  owner to timer mode and checks the first real delegation there.
- 2026-10-03 (step 4): delegations keep their own ledger `~/skills/owner/<repo>/delegations.jsonl` (running, waiting
  at the limit, landed, error); a worker counts as landed when its slot has no CURRENT_PLAN and nothing off main 30
  min after its start, and stop.py ends its session only when it is idle (stop.py refuses busy ones).
- 2026-10-03 (step 5): a task is machine-run only in the strict form (Check: backticked commands only; Act:
  commands and `notify|delegate|wake` only; optional **Still failing**); anything else is prose and wakes the model,
  so a task written before the form never runs a command by accident (hal2's live n8n Check names an uninstalled
  `hal2-cli-n8n` and would have fired the production redeploy).
- 2026-10-03 (step 5): hal2's OWNER-ROLE.md is the user's file (the handoff's rule): the converted tasks are a
  proposal, [owner-role-hal2-tasks.md](owner-role-hal2-tasks.md) (also in `~/skills/owner/hal2/pending/`), applied
  by the user; until then the tick wakes the model for them as today.

## Notes
- Step 1 (2026-10-03): `owner.py start-check|tick [--dry-run]|mode`, `tick.py` (the frame: planned actions as data,
  `execute`, `summarize`), `due.record_run` (a round records its runs at its own `now`). Duties and tasks without a
  handler are planned as `wake` items `no-handler`, so the frame runs end to end before steps 2-5 fill the handlers
  (`owner.HANDLERS`). A live dry run in hal2's owner slot planned all 9 items. Trap: `git status --porcelain` needs
  its leading space kept (`tick.git` does not strip it).
- Step 2 (2026-10-03): `boss.py` (the boss's rules as `Planner`, keyed actions deduplicated against the log:
  wake → release after 10 min, priority front/land-now/clear, load pause → go when the landing ends, waiter-gone,
  flaky under load → `delegate`, else wake, orphan with HANDOFF.md → `worktree run --prompt "/handoff c"`; active-long,
  work-not-queued, long-queue and paused wake at most hourly), `deliver.py`, `snapshot(fetch=False)` for dry runs.
  `active-long` stays J for now (reading the landing's step is step 3's kind of work).
- Step 3 (2026-10-03): `duties.py` (lead: no-plan, context-high, a stop announcing its next step → continue, failed
  without the watch duty; ci: a transient main-red reruns once (regex over `--log-failed`), a real one is
  delegated, slot-red told; watch: sanity-watch's `find_incidents` imported (its CLI writes its heartbeat), resume
  typed into the `failed` session, never into a landing, count/escalate/handover recorded; autoclear:
  `evidence.py doctor --json`/`doctor_items`, the same resting session continued with clear-and-continue, one
  delegation per reason), `tick.context` (agents, panes, landings once per round). The live dry run planned only
  wakes for real questions and waits.
- Step 4 (2026-10-03): `delegation.py` (brief template with the evidence as data, the limit from `worker_limit`,
  free.py's idle session first (prompt typed by deliver.py), else create.py, the worker prompt of SKILL.md, the
  ledger, `follow_up`: landed workers recorded and stopped, waiting briefs started when there is room), the tick
  places its `delegate` actions after the duties and follows up every round, `owner.py delegate --brief --title`
  for a brief the woken model writes.
- Step 5 (2026-10-03): `tasks.py` (parse, plan_task: check → record, else the Act's commands, `notify`, `delegate`,
  `wake`, then `owner check task <name>` again with `on_fail` = the Still-failing outcomes; built-in `owner check
  flaky|orphans`), the executor's `cwd` and `on_fail`, `task:*` handlers, `due.py check` prints each task's mode.
  Trap: hal2's `code/python/scripts/hal9k/main.py` is not executable, the proposal runs it with `python3`.

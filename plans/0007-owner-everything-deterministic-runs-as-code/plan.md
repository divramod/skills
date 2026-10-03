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
| 6 | `needs_model` + wake: tick writes `~/skills/owner/<repo>/wake.json` (items, evidence, instruction paths) and wakes the owner session (`hal2-cli-agents send <pane> "/owner act"`) only when it is non-empty; `/owner act` reads only that | a quiet tick adds no turn to the owner's transcript; an injected J item wakes it once | done |
| 7 | External timer: `owner.py install-timer` (launchd on macOS, systemd user timer on Linux) at `loop_cron`; `/owner start` installs it, `/owner stop` removes it; Claude cron no longer used | `launchctl list` names the owner's timer; ticks appear in the log every interval with the session idle | done |
| 8 | Skill text split: SKILL.md down to start/stop/act/authority, `instructions/<kind>.md` per J kind, subskills only for the woken parts; README and description updated | SKILL.md under 8 KB; every J kind has its instruction file; check-plugins passes | done |
| 9 | Measure: one hour of ticks on hal2, model tokens of the owner session before vs after | the owner's transcript shows ≤ 1 wake per real J item; noted in the plan | done (goal missed, see 9a–9c) |
| 9a | Noise: an idle-in-plan stop or an F6 judge in a slot that waits in the merge queue or is paused for a landing is no wake (`tick.waiting_noise`, `tick.paused`) | tests; a dry run plans no such wake | done |
| 9b | Small context per wake: the tick types `/clear` before `/owner act` when the owner's context passes 10% (`wake.small_context`); Act records open threads in the log | tests with a fake session | done |
| 9c | Measure again: one hour of ticks after 9a/9b against the 11:15–12:15 baseline | model input per hour well below the baseline (target ≤ 20%); ≤ 1 wake per real J item | next |
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
- 2026-10-03 (user): the task proposal is applied: hal2's OWNER-ROLE.md in the owner slot has the four tasks in the
  machine form (c48f5625 on branch `owner`, committed by this session on the user's go); `due.py check`: all four
  run by the tick.
- 2026-10-03 (step 6): wake.json accumulates items (`seq`) until the session drops the handled ones (`owner.py
  wake --done <seq>`); the session is woken once per batch, a refused wake retried next tick, an unacted wake
  repeated after an hour. Each item names one instructions file: `instructions/<kind>.md` (step 8), else its duty's
  SUBSKILL.md, else SKILL.md. Failed delegations become `delegate-failed` wake items.
- 2026-10-03 (step 7): the timer is `owner.py timer install|remove|status` (not `install-timer`): launchd agent
  `local.owner.<repo>` with one StartCalendarInterval per minute of `loop_cron` (always hourly-shaped), a systemd
  user timer on Linux; PATH and OWNER_DIR are taken from the installing shell; `timer.json` keeps the installed
  cron and a tick reinstalls when OWNER-ROLE.md changed it; tick output to `tick.log` (rotated at 1 MB). Its
  live check runs on a throwaway repository with its own OWNER_DIR, since hal2's owner still runs the Claude loop.
- 2026-10-03 (step 8): instructions are per duty, not per kind (lead's kinds come from lead_scan and a task's kind
  is its name): `instructions/<duty>.md` for mtm, lead, ci, watch, autoclear, task, frame and owner, an optional
  `instructions/<duty>.<kind>.md` for a kind that needs its own; wake.py looks them up in that order.
- 2026-10-03 (step 8): hal2's owner switches to timer mode (step 9's switch) before step 8 trims the subskills: the
  Claude loop reads them until it is gone. Step 8 writes the instructions first, then the switch, then the trim.
- 2026-10-03 (step 9): fewer rounds alone save little: a call re-reads the session's whole context (~430k tokens at
  55%), so the owner session is cleared before a wake (9b) instead of handed off at 50%; its state is in files and
  Act records open threads. hal2's clear-and-continue cannot do it (it needs a plan with steps left), so the tick
  types `/clear` into the empty prompt itself and waits for the new session. Slots waiting in the queue or paused
  are not judgment (9a): the owner answered "they wait" for each of them.
- 2026-10-03 (user): the empty-prompt check moves into hal2 as `hal2-cli-agents send --if-empty` (shot
  plugin-agents 29); once it lands, `deliver.py` calls it and drops its Python copy.

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
- Step 6 (2026-10-03): `wake.py` (items, `hand_over`, `done`, `owner_pane`: the agent whose checkout is the owner
  slot), `tick.run` hands over after the delegations (a dry run lists `wake_items` only), `owner.py wake [--done]`,
  SKILL.md's `/owner act`. Live dry run in hal2's owner slot: 12 J items (long queue, a question, idle-in-plan,
  F6 judges), each with its instructions file; `owner_pane` finds the owner (%127). 72 tests pass.
- Step 7 (2026-10-03): `timer.py`, `owner.py timer install|remove|status`, `follow_cron` after each tick, SKILL.md's
  loop installs the timer. Live: a throwaway repository's owner slot (own OWNER_DIR), `launchctl list` named
  `local.owner.ownertest`, launchd ran ticks at 11:47 and 11:52 (exit 0, quiet, no wake), then removed. 77 tests.
- Step 8 (2026-10-03, part 1): `instructions/<duty>.md` for mtm, lead, ci, watch, autoclear, task, frame, owner (the
  woken parts only). The user's go for the switch: the owner session hands off and deletes its cron job first, then
  `owner.py timer install` in its slot; then the subskills are trimmed and SKILL.md split.
- Step 8 (2026-10-03, part 2): hal2's owner switched to timer mode at 12:30 (the owner session handed off and
  deleted its cron first; slot 11's open `ask` already held its orphan restart, an `ask` recorded for 04). SKILL.md
  8048 bytes (start, stop, act, authority, calls), `reference.md` (OWNER-ROLE.md, owner branch, log, delegation by
  hand, decisions, moved verbatim), the subskills reduced to pointers, merge-to-main-boss's to the procedures the
  woken session links; README. First live tick 12:38: 14 items, one wake, the owner handled them in ~1 min; it found
  the owner's own slot planned as `lead/asks` (fixed: da473c5).
- Step 9 (2026-10-03): 14:35–15:35 under the timer (after the user's offline gap 12:40–14:20): 10 turns (3 wakes, 6
  peer messages, 1 other), 63 calls, 27.45M input, 35.3k output, against the Claude loop's 11:15–12:15: 9 turns, 82
  calls, 26.06M input, 41.6k output. Wakes: one per tick with items (14:53 two, 15:13 eleven, 15:22 ten); 07's F6
  judge came in two wakes (paused, not real J), and most lead items were queue waiters. The owner handled each wake in
  1–3 min. Causes and fixes: 9a, 9b.

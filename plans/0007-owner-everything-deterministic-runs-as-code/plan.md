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
| 2 | The D/T actions of merge-to-main-boss in `tick` (priority front, wake → release rule, waiter-gone, load-high pause/go, flaky ledger, work-without-agent with HANDOFF), messages through `hal2-cli-agents send` to idle sessions only | tests per action on fixtures; a dry run on the live queue names the right actions | next |
| 3 | The D/T actions of development-lead, ci (transient-rerun regex, runners, hung runs, slot-red), watch (sanity-watch `scan.py resume`), autoclear (known continuations) | tests per action; dry runs on live data | |
| 4 | Delegation as code: `owner.py delegate --brief`, briefs from templates, limit, free/new slot, prompt, log; `follow-up` (landed → stop idle worker) | a fixture test spawns nothing but prints the exact create.py/free.py calls; one live delegation in hal2 logged | |
| 5 | OWNER-ROLE.md tasks with machine-readable Check/Act (a command in backticks runs; `notify`, `delegate`, prose = wake); hal2's four tasks converted (in the owner branch) | `due.py check` validates the new form; tick runs hal2's tasks with no wake | |
| 6 | `needs_model` + wake: tick writes `~/skills/owner/<repo>/wake.json` (items, evidence, instruction paths) and wakes the owner session (`hal2-cli-agents send <pane> "/owner act"`) only when it is non-empty; `/owner act` reads only that | a quiet tick adds no turn to the owner's transcript; an injected J item wakes it once | |
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

## Notes
- Step 1 (2026-10-03): `owner.py start-check|tick [--dry-run]|mode`, `tick.py` (the frame: planned actions as data,
  `execute`, `summarize`), `due.record_run` (a round records its runs at its own `now`). Duties and tasks without a
  handler are planned as `wake` items `no-handler`, so the frame runs end to end before steps 2-5 fill the handlers
  (`owner.HANDLERS`). A live dry run in hal2's owner slot planned all 9 items. Trap: `git status --porcelain` needs
  its leading space kept (`tick.git` does not strip it).

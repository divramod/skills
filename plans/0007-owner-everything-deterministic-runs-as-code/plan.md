# Plan 0007: owner: everything deterministic runs as code

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
| 1 | `owner.py` skeleton: `start-check` and `tick` running the round frame (stay current, the OWNER-ROLE.md edit, due, a log line per action, the summary from the log), plus `--dry-run` | `python3 skills/owner/scripts/owner.py tick --dry-run` in the owner slot prints the due items and the planned actions; unit tests pass | next |
| 2 | The D/T actions of merge-to-main-boss in `tick` (priority front, wake → release rule, waiter-gone, load-high pause/go, flaky ledger, work-without-agent with HANDOFF), messages through `hal2-cli-agents send` to idle sessions only | tests per action on fixtures; a dry run on the live queue names the right actions | |
| 3 | The D/T actions of development-lead, ci (transient-rerun regex, runners, hung runs, slot-red), watch (sanity-watch `scan.py resume`), autoclear (known continuations) | tests per action; dry runs on live data | |
| 4 | Delegation as code: `owner.py delegate --brief`, briefs from templates, limit, free/new slot, prompt, log; `follow-up` (landed → stop idle worker) | a fixture test spawns nothing but prints the exact create.py/free.py calls; one live delegation in hal2 logged | |
| 5 | OWNER-ROLE.md tasks with machine-readable Check/Act (a command in backticks runs; `notify`, `delegate`, prose = wake); hal2's four tasks converted (in the owner branch) | `due.py check` validates the new form; tick runs hal2's tasks with no wake | |
| 6 | `needs_model` + wake: tick writes `~/skills/owner/<repo>/wake.json` (items, evidence, instruction paths) and wakes the owner session (`hal2-cli-agents send <pane> "/owner act"`) only when it is non-empty; `/owner act` reads only that | a quiet tick adds no turn to the owner's transcript; an injected J item wakes it once | |
| 7 | External timer: `owner.py install-timer` (launchd on macOS, systemd user timer on Linux) at `loop_cron`; `/owner start` installs it, `/owner stop` removes it; Claude cron no longer used | `launchctl list | grep owner` shows it; ticks appear in the log every interval with the session idle | |
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

## Notes

- Not grilled yet: run one autogrill round (or `/grill`) before step 1.

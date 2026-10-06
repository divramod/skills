# Plan 0011: farmer tick respects autoclear off and runs faster

Grilled: 2026-10-06 (autogrill ×1)

Landing: auto

Created 2026-10-06. `plans/CURRENT_PLAN` names the active plan; helper files for this plan live next to this file.

## Goal

The farmer's autoclear duty and fix-autoclear's doctor never act on a session whose autoclear the user switched off, and a farmer tick shows per duty where its time goes and runs a full round (every duty due) well under a minute.

## Context

- Brief (farmer of hal2, 2026-10-06, runtime state, not committed): `~/.hal/git/worktree/hal2/farmer-hal2/roles/farmer/briefs/2026-10-06-farmer-tick-autoclear-off-and-speed.md`
- Servant role: `~/.hal/git/worktree/hal2/farmer-hal2/roles/farmer/servants/farmer-tick-respects-autoclear-off-and-runs-faster.md` (Farmer: farmer-hal2 (hal2), session farmer-hal2-71)
- [.adr/deterministic-first.md](../../.adr/deterministic-first.md): the tick does the rule-based work as code
- Code: `skills/fix-autoclear/scripts/evidence.py` (`doctor_items`), `skills/farmer/scripts/duties.py` (`plan_autoclear`),
  `skills/farmer/scripts/tick.py` (`run`, `summarize`), `farmer.py` (`run_tick`, `print_round`), `mtm_ci.py`,
  `ci_scan.py`, `trains.py`, `mtm_scan.py` (`snapshot`), `prune.py` (`SIZES_EVERY`: du over every worktree)
- hal2: `code/rust/libs/hal2-agents/src/guard.rs` (`Marker`, `cancel_marker`: rearm = max(percent, threshold) + 5),
  `sweep.rs` (`MAX_ATTEMPTS` = 3: the sweep's give-up always writes `attempts >= 3` with `gave_up`); shot
  plugin-agents #31 (a per-session `autoclear off` switch, `autoclear_off: true` in `hal2-cli-agents list --json`)
- Incident: guard marker `227f49f1-0b95-4ea0-af2f-b55a9b6a9917.guard` (hal2 wt 02, pane %171): `stage cancelled,
  percent 22.0, threshold 35, rearm_percent 1000, gave_up true`, no `attempts`; the farmer's `duty:autoclear` ran
  clear-and-continue on it at 2026-10-06T10:10:02 (job 171, cancelled by 02 at 10:12); global shot fix-autoclear #9

## Steps

Each step is detailed when it is next; keep one line per step here. The plan lands once, after all its steps
(`Landing: auto`: the plan skill runs `/mtm` then); steps checked only after the landing come last, their done-when
starting "after the landing: ...".

| # | Step | Done when | Status |
|---|---|---|---|
| 1 | Autoclear off is skipped: `evidence.autoclear_off(marker, agent)` (a `gave_up` marker the sweep never wrote: `attempts` below hal2's `MAX_ATTEMPTS` 3, or `rearm_percent >= 100`, or the agent's `autoclear_off: true`); `doctor_items` leaves those sessions out (listed apart as `off`), `duties.plan_autoclear` skips any problem whose session is off; regression tests replay 227f49f1's marker in test_evidence.py and test_duties.py; fix-autoclear's cases.md and SKILL.md record the case | `python3 -m unittest discover -s skills/fix-autoclear/scripts && python3 -m unittest discover -s skills/farmer/scripts` green; `python3 skills/fix-autoclear/scripts/evidence.py doctor --hours 24 --json` names neither 227f49f1 nor da8d4b47 as a problem | done |
| 2 | Per-duty timing: `tick.run` times the frame (merge-from-main, role edit), each due item (its planning plus its actions' execution), acks, delegations, wake and summary; `print_round` writes one `timing:` line (tick.log gets it), `--json` a `timing` object; `farmer.py tick --dry-run --all-due` counts every opted-in item due (measurement only, refused without --dry-run); baseline measured on hal2's farmer slot and recorded under Notes | a test asserts the timing line; `python3 skills/farmer/scripts/farmer.py tick --dry-run --all-due --repo ~/.hal/git/worktree/hal2/farmer-hal2` prints a `timing:` line with every duty, its numbers under Notes as "before" | done |
| 3 | Each run's jobs fetched once per round: `gh_runs.py` memoizes `gh run list`/`gh run view --json jobs` per process, caches a completed run's jobs on disk by run id (state folder, pruned after 7 days) and fetches the uncached ones in parallel; `mtm_ci.landings`, `ci_scan.failed_jobs` and `trains.ci_red` use it; the round summary's snapshot reuses the round's fetch | tests for the cache (memo, disk hit for completed runs, a running run refetched, parallel prefetch); farmer tests green; a second `--all-due` dry tick's `timing:` line ends `gh <n> list, <m> view, <k> cached` with views only for running runs | done |
| 4 | Measure the full tick with every duty due and cut what still dominates (by the step-2 timing, e.g. prune's every-6-hours `du` over every worktree, a repeated snapshot); before/after recorded under Notes | `farmer.py tick --dry-run --all-due --repo ~/.hal/git/worktree/hal2/farmer-hal2` total well under 60 s, or Notes name what still dominates and why it stays | next |
| 5 | Docs: farmer's SKILL.md/reference.md (the timing line, `--all-due`, the run-jobs cache), fix-autoclear's SKILL.md (autoclear off is no failure) | `grep -n "timing:" skills/farmer/SKILL.md skills/farmer/reference.md` and `grep -n "autoclear off" skills/fix-autoclear/SKILL.md` both hit | |
| 6 | Write the UATs: `uat.md` beside this file (`plan.py uat`), only the checks a human must do on the default branch after the landing | `plan.py current` shows `uat` with its checks | |

## Pre-authorized

User-only decisions (money, production deploys, accounts and secrets, paid resources, product choices), asked and
answered before implementation, with the user's words and the date; the run acts on them without asking again.

- None needed: the plan changes only the skills repo's scripts and docs; its landing at the end is agreed by the start
  (the farmer's brief, relaying the user 2026-10-06: "tell the farmer to handle that").

## Decisions

All 2026-10-06, autogrill 1 (decided by the skills repo's rules, deterministic-first, the more battle-tested option):

- **What "autoclear off" is** (autogrill 1): hal2 has no explicit per-session switch yet (shot plugin-agents #31).
  A marker is a deliberate off when it can only have been written by hand: `gave_up` with `attempts` below hal2's
  `MAX_ATTEMPTS` (3; the sweep's own give-up always writes `attempts >= 3` together with `gave_up`), or a
  `rearm_percent >= 100` (no context percent ever re-arms it; hal2's `cancel_marker` writes at most
  max(percent, threshold) + 5). Forward-compatible: an agent row with `autoclear_off: true` (what #31 promises in
  `hal2-cli-agents list --json`) is off too. The hal2 side stays with #31; this plan changes no hal2 code.
- **Where it is skipped** (autogrill 1): at the source, `evidence.doctor_items` (the doctor reports failures nobody
  reported; a switched-off session is none), plus defense in depth in `duties.plan_autoclear` (a problem whose
  session's marker or agent says off plans no clear-and-continue and no `/fix-autoclear` delegation). The doctor's
  JSON lists them apart under `off` and its text output counts them, so they stay visible.
- **MAX_ATTEMPTS drift** (autogrill 1): evidence.py keeps hal2's value as a constant; `evidence.py selfcheck`
  compares it with `sweep.rs`, so a changed hal2 value is reported, not silently wrong.
- **Timing line** (autogrill 1): one stdout line per round, `timing: frame 2.1s, duty:mtm 3.0s, ..., total 9.8s`
  (launchd appends stdout to tick.log), sorted in round order; a duty's time is its planning plus the execution of
  its actions; the same numbers as `timing` in `--json`. No separate log file: tick.log already rotates at 1 MB.
- **`--all-due`** (autogrill 1): only with `--dry-run` (a measurement tool; a real round never forces what is not
  due), counts every opted-in duty and task due.
- **Run-jobs cache** (autogrill 1): one module `gh_runs.py` all three callers share; a per-process memo (one tick is
  one process, so: once per round), a completed run's jobs on disk in the state folder (`cache/run-jobs/<id>.json`,
  ignored by the state folder's .gitignore, files older than 7 days pruned), a running run's jobs only memoized
  (fresh next round); uncached runs fetched in parallel with a thread pool of 6 (gh is I/O bound). No change to what
  any caller decides.
- **Summary snapshot** (autogrill 1): `tick.summarize` snapshots with `fetch=False`: the round's merge-from-main
  fetched origin already.

## Notes

- Step 1: the live doctor (`evidence.py doctor --hours 24 --json`) now reports no problem and lists 227f49f1 and
  da8d4b47 under `off`; a real sweep give-up on disk (4100c537: `attempts 3, gave_up`) is the counter-example the
  test keeps reporting. The farmer suite takes ~70 s (199 tests). Step 5's fix-autoclear half (SKILL.md, cases.md)
  was done with step 1.
- Step 2, **before** (2026-10-06 10:21, `farmer.py tick --dry-run --all-due --repo ~/.hal/git/worktree/hal2/farmer-hal2`,
  a dry round: no execution, no summary): `frame 0.2s, context 0.3s, duty:mtm 17.8s, duty:lead 1.8s, duty:ci 1.5s,
  duty:sync 0.1s, duty:prs 3.1s, duty:watch 2.1s, duty:autoclear 1.8s, duty:trains 12.8s, duty:prune 3.1s, task:n8n
  0.2s, task:hal9k production healthy 6.3s, task:Disabled tests come back 0.5s, task:Orphaned slots finished 19.4s,
  delegations 3.1s, total 74.5s`. mtm, trains and the orphans task each run `mtm_scan.snapshot`/`mtm_ci.landings`
  (gh run list plus one serial `gh run view` per not-landed land run); a real round snapshots once more in its
  summary. Prune's disk sizes (`du -sk` over every worktree, timeout 300 s, every 6 h) are not in a dry round's
  numbers when the log holds a recent `prune:disk:` key; step 4 looks at them.
- Step 3 (same command, 10:3x): first round `duty:mtm 7.2s, duty:trains 0.2s, task:Orphaned slots finished 9.7s,
  total 52.4s; gh 2 list, 9 view, 0 cached`; the next round `duty:mtm 5.4s, duty:trains 0.2s, task:Orphaned 9.0s,
  total 41.3s; gh 2 list, 1 view, 8 cached` (one view: the running land run). The timing line ends with the round's
  gh calls (`gh <list> list, <view> view, <cached> cached`) instead of a debug variable. Left for step 4: the orphans
  task (9 s with no gh view), prune 6-7 s, `task:hal9k production healthy` (5-14 s: an ssh status check, the
  task's own work), prs 3-4 s.

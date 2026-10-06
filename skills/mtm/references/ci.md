# Landing through CI

A repository whose default branch (or this worktree's `HEAD`) has `.github/workflows/land.yml` lands through
GitHub Actions (hal2 plan 0131, `.adr/landings-on-github-actions.md` in hal2). Nothing is tested on this machine:
`hal2-cli-git worktree merge-to-main` takes the worktree's turn in the merge queue, merges the default branch in,
builds the `--no-ff` candidate, pushes the branch and `land/<slot>`, opens or updates the landing's pull request
(`land/<slot>` → the default branch) and waits until `land.yml` has tested the candidate: green, its `merge` job
fast-forwards the default branch to the candidate (the PR shows merged); red, the queue stays held for this worktree
until its fix lands (the user, 2026-10-06: "run landing until everything is fixed and merged and then release"). There
is no attempts counter and no `reserve`: SKILL.md's steps 2 and 5 to 8 apply as they are, this page replaces steps
1, 3 and 4.

## Land

Run in the worktree (SKILL.md step 2 first: everything committed and pushed):

**First wait until no land run is unfinished**, before every `merge-to-main` below (the first and every rerun: each
takes the queue and pushes a candidate): `bash $S/land-runs.sh`, in the background like the landing. It runs
`gh run list --workflow land.yml --limit 10 --json databaseId,headBranch,status --jq '.[] | select(.status !=
"completed")'` every minute and exits 0 once that prints nothing; while it lists a run, another landing still runs
or ships (`queued` counts too: a run whose ship job waits for a runner is queued), so never push meanwhile.
`--once` checks a single time (exit 6: runs listed); exit 1: gh failed, nothing is known, check again before
pushing. hal2-cli-git's own check misses queued runs (the user, 2026-10-06: "the mtm skill should have a mention of
the command on how to check in the gh workflow list, if he can start now or needs to wait").

`hal2-cli-git worktree merge-to-main --max-wait 100m --keep-reserved --json [<slot>]`, in the background with the
shell tool's maximum timeout (Claude Code: `run_in_background`, `timeout` 7200000; a lower limit gets a
`--max-wait` 20 minutes below it). It needs `gh` logged in to GitHub (`gh auth status`).

**`/mtm milestone`** (SKILL.md's [milestone mode](../SKILL.md#milestone-mode)): run the same command **without
`--keep-reserved`**, and on exit 0 do not go to step 5 (it is skipped): if the JSON still says `reserved: true`, run
`hal2-cli-git worktree release --json [<slot>]` at once, so the queue is free for the next landing; then go on with
SKILL.md step 6 as milestone mode says.

| Exit | JSON `status` | Do |
|---|---|---|
| 0 | `landed` | the default branch is the candidate (`commit`), the PR (`pull_request`) merged; `retests` counts how often the default branch moved under it. `reserved: true`: go to SKILL.md [step 5](../SKILL.md#5-finish-the-plan-and-land-it). Report `warnings` (e.g. the main checkout could not be pulled) |
| 0 | `nothing` | the branch has nothing the default branch lacks: step 5 |
| 6 | `waiting`, `testing`, `shipping` | the slice passed: in the queue (`ahead`), while the candidate is tested (`candidate`, `run`) or while a run ships (`runs`; with `commit`: this landing has landed and waits for its run's `ship / ...` jobs before it releases the queue: strictly one land run at a time). The place and the candidate are kept: **rerun the same command at once**, as often as it takes |
| 4 | `gate_failed` | the candidate is red; the queue stays held for this worktree (`released: false`): [fix it](#red) and run again at once, the rerun adopts the hold at the head of the queue. Never release it yourself while you can fix: it is released when the branch lands. An older hal2-cli-git answers `released: true`: rerun at once all the same (it queues again) |
| 3 | `conflict` | merging the default branch in conflicts (`files`): resolve as the [mfm](../../mfm/SKILL.md) skill's **Conflicts** says, commit, rerun (the queue stays held for this worktree meanwhile: go straight on) |
| 5 | `stopped`, `cancelled`, `interrupted` | the user ended it: report and stop, never rerun on your own (your own shell's time limit is no user stop: rerun) |
| 1 | `error` | uncommitted changes: SKILL.md step 2. Anything else: report the `message`; the queue may be held for this worktree, so ask the user (fix, or `hal2-cli-git worktree release`) |

**Watch the run every 5 minutes while it is tested** (the user, 2026-10-06). Once the candidate's run is known (exit
6 names `run`; else `hal2-cli-git worktree landings --json`), look at its jobs every 5 minutes
(`gh run view <run> --json jobs`) for as long as the landing waits. A job that concluded `failure` or `timed_out`
while others still run: start on [Red](#red) at once (read its log, reproduce, fix, commit, push) instead of waiting
for the landing to end; the landing keeps its place meanwhile, and when it ends with `gate_failed` the fix is ready
for the next [Land](#land) at once. Never cancel the run: the whole workflow finishes, so every red job of it is
known and fixed in that one next landing (the user, 2026-10-06: "that way we save time"). A red outside the code (runner offline, full disk, network): tell the farmer
right away.

## Red

`gate_failed` lists the `red` jobs, each with its `url` (the job's log) and `reproduce`, the command that runs the
same job in this checkout (`code/bash/scripts/gate/main.sh <job>`):

1. Read why: `gh run view <run id> --log-failed` (the run is the JSON's `run`), or the job's `url`.
2. Reproduce locally with `reproduce` when the log does not make the cause plain (it runs the same script as CI;
   a macOS-only job needs this Mac's Xcode, a stack job Docker).
3. Fix the cause in this worktree (the code, a test; the gate script or the workflow only when they are wrong, and
   say so), commit with a real message, push, and run [Land](#land) again. Only the red jobs and what the fix
   changed run again: jobs and packages whose content key was green before are skipped (green markers).

A job red for a reason outside the code (the runner offline, a network failure, a full disk) is no code fix: rerun
the landing once; when it is red the same way again, report it and ask the user (the farmer's ci duty may already
be on it). Keep going until the PR is merged: every fix is a new candidate, and the queue stays held for this worktree
meanwhile, so every other landing waits on you: fix and run again at once.

## After the landing

land.yml's `merge` pushes the version tags; the same run's `ship / ...` jobs (ship.yml, called after `merge`) promote
the staged Linux bundle, install the landed apps on the Mac host (cargo installs, hal2-api/hal2-daemon, the apps'
install) and pull the main checkout; the landing pulls it too when ship has not yet. hal2-cli-git decides the landing
once `merge` completed: a `ship / ...` job never delays or reddens it. In the report, name the PR and the land run
(its `ship / publish` and `ship / deliver` state), not hook tasks or durations of local steps.

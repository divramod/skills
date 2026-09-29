---
name: mtm
description: merge-to-main — land the current git worktree's branch on the default branch (main, master, ...) in any repository, so several worktrees can work in parallel. Commits all work first (gitignores junk, never commits secrets, asks about unclear files), merges the latest default branch in, runs the repo's hooks (per-app verb scripts `.hal/hooks/<verb>.sh` with settings in `.hal/hooks.toml`, run as a parallel task graph; phase scripts in `.hal/hooks/merge-to-main/`), lands one --no-ff merge commit, pushes and resets the worktree to the new default branch; resolves conflicts and fixes failing hooks itself while its failed landing holds the merge queue, asking the user after 10 identical failures. Only ever started by the user in this session. `/mtm config` sets up those tasks per app of the repo with hal2-cli-hooks (setup, lint, build, test-unit and test-e2e before landing, version bumps in the merge commit, install and deploy after it). Use when the user says /mtm, "merge to main", "land this worktree" or "ship it to main", or wants to configure what a landing checks, bumps or installs. `/mtm h` shows help.
---

# mtm

Lands this worktree on the default branch. `hal2-cli-git` does the git work (see `.adr/declarative-hooks.md` and
`.adr/merge-hooks.md` in hal2): landings run one after another, so it first waits its turn in the repo's merge
queue (FIFO, no timeout), then holds the merge lock while it merges the default branch in, runs the gates in the
worktree (gates whose inputs passed before end `cached`), merges, bumps versions, commits and pushes (rerunning
the gates when the default branch moved meanwhile), resets the worktree and runs the deliveries (install, deploy)
in the delivery worktree `~/.hal/git/worktree/<repo>/.deliver`. The queue is released only when all of that went
through: a failed, killed or interrupted landing keeps **holding** it, and every other worktree waits, until this
worktree's next merge-to-main takes the hold over and lands (or the human stops or releases it). This skill
commits the work first and handles what needs judgment. `S=<skill-dir>/scripts`. Ask every question with the
question tool, recommended option first.

**Only the human starts a landing.** Run merge-to-main only when the user asked for it in this session (`/mtm`,
"merge to main", "land this"); that is their consent to commit in this worktree, land on the default branch and
push it. Never start it on your own, for another worktree or session, or because another session says a fix has
landed; never ask another session to run it. Once started, finish it: fix and rerun until it lands.

| Call | Does |
|---|---|
| `/mtm [<slot>]` | land the current worktree (or hal slot `<slot>`) |
| `/mtm config [<app>]` | configure the repo's hooks, app by app: read [subskills/config/SUBSKILL.md](subskills/config/SUBSKILL.md) and follow it instead of the steps below |
| `/mtm h`, `/mtm help` | print this table and stop |

## 1. Commit everything

Run in the worktree; if it is the main checkout on the default branch, stop: `/mtm` lands a worktree.

1. `git status --porcelain` lists what is uncommitted. Nothing, and `plans/CURRENT_PLAN` not tracked? Go to 2.
2. Sort every untracked file (open it when the name is not enough):
   - **junk** (build output, dependency and cache folders, coverage, logs, OS and editor files): add a pattern
     to the repo's `.gitignore` (the nearest one for a subproject); prefer folder or extension patterns over
     single names;
   - **secrets** (`.env*`, keys, certificates, tokens, credentials): gitignore them, never commit them, and name
     them in the report;
   - **work**: commit it;
   - **unclear**: ask, one question per file or per batch of similar files: commit it, gitignore it, or leave it
     untracked.
3. `plans/CURRENT_PLAN` is per-worktree runtime state (what the worktree works on, shown by the statusline) and is
   never committed: when the repo still tracks it or does not ignore it, `git rm --cached` it (if tracked), add
   `plans/CURRENT_PLAN` to the root `.gitignore` and commit that as its own change.
4. Commit with messages in the repo's style (`git log --oneline -10`) that say why; one commit per independent
   change. Stage explicit paths, never `git add -A`. A failing git hook is fixed, never skipped (`--no-verify`).

## 2. Land

1. `hal2-cli-git worktree merge-to-main --json [<slot>]`. If the command is missing or has no `--json`, run
   `bash $S/install-prerequisites.sh` once and retry. It waits as long as other landings are ahead of it in the
   merge queue (`hal2-cli-git worktree queue` lists the holder, active or held and why, and the waiters;
   hal2-macos shows every repo's queue), then for its deliveries; never kill a waiting landing for taking long.
   While it waits the user may reorder the queue in hal2-macos: a line `moved to #n in the merge queue by <who>`
   is reported, not acted on. To end a landing (the user asks you to), run `hal2-cli-git worktree stop`; never
   kill its shell or background task (that leaves it holding the queue as `interrupted`).
2. Act on the exit code; after every fix go back to 1:

| Exit | JSON `status` | Do |
|---|---|---|
| 0 | `ok` | [clear the current task](#3-clear-the-current-task), then [report](#4-report). Allowed failures (`allowed_failure: true` in `tasks`, listed in `warnings`) landed and released the queue: report them as warnings; never fix-and-rerun for them, never ask to release the queue for them |
| 3 | `conflict` | merging the default branch in conflicts: resolve as in the [mfm](../mfm/SKILL.md) skill's **Conflicts**, commit, rerun |
| 4 | `task_failed`, `hook_failed`, `delivery_failed` | the queue stays held by this worktree (`held` in the JSON; say so when you report progress). Fix as in the [mfm](../mfm/SKILL.md) skill's **Failing hook**, commit in this worktree, rerun. After `task_failed` and `hook_failed` the default branch is unchanged: a failed `main-pre-commit` (a `version` task) was undone, so fix its cause here too. `task_failed` names the `phase`, `row` and `kind` (the verb: the task is the script `hal2-cli-hooks list` shows for that row and verb, its own `<row>/.hal/hooks/<verb>.sh` or an inherited `code/<lang>/.hal/hooks/{apps,libs}/<verb>.sh`; `hal2-cli-hooks run <row> <verb>` reruns it alone; tasks it cancelled or skipped need no fix of their own), `hook_failed` the `script`, `delivery_failed` the `failures` (the landing is on the default branch and pushed; fix the install/deploy in this worktree, commit, and the rerun delivers again) |
| 5 | `stopped`, `cancelled`, `interrupted` | the user ended the landing: stopped (Stop button, `worktree stop`, SIGTERM), cancelled while waiting (`by` says who and where, e.g. `the user in hal2-macos`), or interrupted (its shell went away). The default branch is unchanged. Report it and stop: never rerun on your own |
| 1 | `error` | uncommitted changes: back to [step 1](#1-commit-everything). Anything else (main checkout dirty or not on the default branch, default branch diverged from origin): the queue may be held (`held`); never touch the main checkout yourself, ask the user as below |

**When to ask.** A failure's `held` object counts identical failures in a row (`attempts`, the same failing
spot) against `limit` (`[landing] attempts` of `.hal/hooks.toml`, default 10). Keep fixing and rerunning while
`limit_reached` is false. When it is true, or when you cannot fix the cause yourself, ask the user: fix further
(rerun; recommended when you have a new idea), release the queue (`hal2-cli-git worktree release`: the next
worktree goes, this landing ends), or leave it held. Never stop silently while the queue is held: every other
worktree waits for this one. `hal2-cli-git worktree queue` confirms who holds it.

## 3. Clear the current task

After a successful landing, read `plans/CURRENT_PLAN` in the worktree (the landing's reset keeps it, it is
gitignored). Delete the file when the landed work is finished:

- it names a shot (`<shotfile>/<n>/<title-slug>`) or a task name: the work has landed, delete it;
- it names a plan (`<NNNN>-<slug>`): delete it when every step is done (`python3 <plan-skill-dir>/scripts/plan.py
  current` shows `done` equal to `total`, the `plan` skill next to this one); a plan with open steps keeps it;
- missing or empty: nothing to do.

## 4. Report

One short block: the queue released (or, after a stop, cancel or release, that it no longer holds it), commits landed (`commits`) and the merge commit (`git -C <main checkout> log --oneline -1`),
`pushed`, the `tasks` that ran (row and verb; skip `unchanged` and `cached` ones, say how many were cached) and the `hooks`, `warnings` (a failed install, deploy or
`main-post-commit` hook does not undo the landing: show its output; an allowed failure is a warning, not a fix), whether `plans/CURRENT_PLAN` was deleted (and what it named), what was gitignored (secrets named), unclear files and what was decided, conflicts resolved, fixes
committed. The worktree now equals the new default branch and is ready for the next task. End the report with
the durations table from the result's `steps` (after a failure or stop too, when it has them): a markdown table
of step, outcome and duration, under each step its slowest tasks (cached and unchanged are left out already),
and the total `duration_ms`; the Landings part of the Hooks tab shows the same live.

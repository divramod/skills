---
name: mtm
description: merge-to-main — land the current git worktree's branch on the default branch (main, master, ...) in any repository, so several worktrees can work in parallel. Commits all work first (gitignores junk, never commits secrets, asks about unclear files), merges the latest default branch in, runs the repo's hooks (per-app verb scripts `.hal/hooks/<verb>.sh` with settings in `.hal/hooks.toml`, run as a parallel task graph; phase scripts in `.hal/hooks/merge-to-main/`), lands one --no-ff merge commit, pushes and resets the worktree to the new default branch; resolves conflicts and fixes failing hooks itself. `/mtm config` sets up those tasks per app of the repo with hal2-cli-hooks (setup, lint, build, test-unit and test-e2e before landing, version bumps in the merge commit, install and deploy after it). Use when the user says /mtm, "merge to main", "land this worktree" or "ship it to main", or wants to configure what a landing checks, bumps or installs. `/mtm h` shows help.
---

# mtm

Lands this worktree on the default branch. `hal2-cli-git` does the git work under a per-repo merge lock (merge
the default branch in, the hooks, the merge, the push, the reset; see `.adr/declarative-hooks.md` and
`.adr/merge-hooks.md` in hal2); this skill
commits the work first and handles what needs judgment. Calling `/mtm` is the user's consent to commit in this
worktree, land on the default branch and push it. `S=<skill-dir>/scripts`. Ask every question with the question
tool, recommended option first.

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
   `bash $S/install-prerequisites.sh` once and retry. It may wait up to 10 minutes for another merge's lock.
2. Act on the exit code; after every fix go back to 1:

| Exit | JSON `status` | Do |
|---|---|---|
| 0 | `ok` | [clear the current task](#3-clear-the-current-task), then [report](#4-report) |
| 3 | `conflict` | merging the default branch in conflicts: resolve as in the [mfm](../mfm/SKILL.md) skill's **Conflicts**, commit, rerun |
| 4 | `task_failed`, `hook_failed` | fix as in the [mfm](../mfm/SKILL.md) skill's **Failing hook**, commit in this worktree, rerun. The default branch is unchanged: a failed `main-pre-commit` (a `version` task) was undone, so fix its cause here too. `task_failed` names the `phase`, `row` and `kind` (the verb: the task is the script `hal2-cli-hooks list` shows for that row and verb, its own `<row>/.hal/hooks/<verb>.sh` or an inherited `code/<lang>/.hal/hooks/{apps,libs}/<verb>.sh`; `hal2-cli-hooks run <row> <verb>` reruns it alone; tasks it cancelled or skipped need no fix of their own), `hook_failed` the `script` |
| 1 | `error` | uncommitted changes: back to [step 1](#1-commit-everything). Anything else (main checkout dirty or not on the default branch, default branch diverged from origin, lock held too long): report the `message` and stop. Never touch the main checkout yourself |

Stop after **3 runs in a row that fail the same way** (same hook and error, or the same conflict): report what
fails and what you tried.

## 3. Clear the current task

After a successful landing, read `plans/CURRENT_PLAN` in the worktree (the landing's reset keeps it, it is
gitignored). Delete the file when the landed work is finished:

- it names a shot (`<shotfile>/<n>/<title-slug>`) or a task name: the work has landed, delete it;
- it names a plan (`<NNNN>-<slug>`): delete it when every step is done (`python3 <plan-skill-dir>/scripts/plan.py
  current` shows `done` equal to `total`, the `plan` skill next to this one); a plan with open steps keeps it;
- missing or empty: nothing to do.

## 4. Report

One short block: commits landed (`commits`) and the merge commit (`git -C <main checkout> log --oneline -1`),
`pushed`, the `tasks` that ran (row and verb; skip `unchanged` ones) and the `hooks`, `warnings` (a failed install, deploy or
`main-post-commit` hook does not undo the landing: show its output), whether `plans/CURRENT_PLAN` was deleted (and what it named), what was gitignored (secrets named), unclear files and what was decided, conflicts resolved, fixes
committed. The worktree now equals the new default branch and is ready for the next task.

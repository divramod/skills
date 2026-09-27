# mtm config

Sets up what a repository's landings and merges run, app by app: tasks in `.hal/hooks.toml` (setup, format,
lint, build, test, version, install, deploy), run by `hal2-cli-git` only for changed code and managed with
`hal2-cli-hooks`. The model, the commands, recipes and hal2's configuration are in
[references/hooks.md](../../references/hooks.md): read it before proposing tasks.

Run `hal2-cli-hooks` in the worktree (`H=hal2-cli-hooks`; missing? `bash <skill-dir>/scripts/install-prerequisites.sh`).
`hooks.toml` changes land with the next `/mtm` like any other work (calling `/mtm config` is no consent to
land). Ask every question with the question tool, recommended option first.

| Call | Does |
|---|---|
| `/mtm config` | walk every app of the repo and configure its tasks |
| `/mtm config <app>` | only that app (a row from `hal2-cli-hooks list`) |

## 1. Inventory

1. `$H list --json`: every row (`code/<language>/apps/<name>`, shared workspaces, libs no workspace covers, or
   the repo itself as one app), its `stacks`, `workspace`, `members` and the tasks already configured.
2. Script hooks in `.hal/hooks/merge-to-main/` (hand-written, or a `lib.sh` + `parts/` dispatcher)? Migrate them
   first (reference: *Migrating script hooks*), including stamps for deliveries that are already current.
3. `$H suggest`: what the presets propose per row. It is the starting point, not the answer.

## 2. Per app

Go through the apps one by one (libs and workspaces with the apps that build from them). For each, find out
before asking, from the app's files, its README and the repo's CLAUDE.md/INTENT.md:

- **how it is set up and checked**: its install, format, lint, build and test commands, and how long they take
  (run them once: a gate that takes minutes still belongs before the landing when nothing cheaper covers it,
  but say so);
- **how it is delivered**: installed from the main checkout (`cargo install --path`, an app bundle, a launchd
  service), run straight from the main checkout (no install), or published elsewhere (never publish from a task
  without the user asking for it);
- **what it is built from**: shared libs, build scripts, assets, pages it bundles: they go into the row's
  `paths` (cargo path dependencies are added automatically);
- **what it shares**: a workspace whose checks cover several apps keeps them on its `workspaces.<name>` row,
  checked once (`$H gates <workspace> per-app` only when the apps need different gates).

Then propose the app's tasks in one question per app: each kind with its command, `cwd`, `ignore` (tests don't
trigger installs or bumps) and whether it is on, recommended set first. Write the chosen ones with
`$H set <row> <kind> --run ... [--cwd] [--paths] [--ignore] [--timeout]`, row `paths` by editing
`.hal/hooks.toml` (comments survive every `hal2-cli-hooks` edit). A version bump or anything longer than a command
line goes into a commented script under `.hal/hooks/scripts/`. A delivery that is already current on this
machine gets a stamp (`$H stamp <row> install --set <commit>`), so the next landing does not redeliver it.

## 3. Verify

1. `$H check`: no errors, and no warnings you cannot explain.
2. Try every new or changed task:
   - gates: `$H run --phase worktree-pre-merge --all` (or `$H run <row> <kind>` per task) in this worktree; they
     must pass on the current code and leave `git status` unchanged (a gate that writes files fails the
     landing: gitignore its output). Without `--all` it shows the change detection: only rows the branch
     touched run.
   - setup: `$H run <row> setup`.
   - version: `$H run <row> version` edits files in this worktree: check the diff, then `git checkout` it.
   - install and deploy do what a landing does (installs, restarts): ask before `$H run <row> install`.
3. When the user asks for a deep test: rehearse real landings in a sandbox clone, one per scenario (reference:
   *Rehearsing landings*).
4. Commit `.hal/hooks.toml` and any scripts in the worktree with a message in the repo's style.

## 4. Report

A table of the rows and their tasks (kind, what it runs, on or off), stamps recorded, what was tried and its
result, what was not tried and why, and anything left open (an app without a gate, a slow gate).

# mtm config

Sets up a repository's merge-to-main hooks, app by app. `hal2-cli-git worktree merge-to-main` runs
`.hal/hooks/merge-to-main/<phase>.sh`; `/mtm config` installs a managed dispatcher there that runs one folder per
**part** (an app, or a workspace several apps share): `parts/<part>/paths` (the part's files as git pathspecs) and
any of `worktree-pre-merge.sh`, `main-pre-commit.sh`, `main-post-commit.sh`. The layout, the helpers and worked
examples are in [references/hooks.md](../../references/hooks.md): read it before proposing hooks.

`H=<skill-dir>/scripts/hooks.py` (all subcommands take `--repo <dir>`, default: the current checkout). Run it in
the worktree; hook changes land with the next `/mtm` like any other work (calling `/mtm config` is no consent to
land). Ask every question with the question tool, recommended option first.

| Call | Does |
|---|---|
| `/mtm config` | walk every app of the repo and configure its hooks |
| `/mtm config <app>` | only that app (a name from `hooks.py apps`) |

## 1. Inventory

1. `python3 $H apps`: the apps and libs (`code/<language>/{apps,libs}/<name>`, or the repo itself as one app when
   it has no such folders), each with its `stack` (cargo, bun, swiftpm, xcodegen, plenary, ...), `scripts` (a
   package.json's), `workspace` (a Cargo workspace it belongs to) and the `parts` already covering it; `managed`
   says whether the dispatcher is installed.
2. Not managed and phase files exist? They are hand-written hooks: move each one's work into a part (its path
   list into `parts/<part>/paths`, its body into `parts/<part>/<phase>.sh`, see the reference's *Migrating*),
   `git rm` the old files, then continue.
3. `python3 $H init` installs or updates the dispatcher (`lib.sh` and the three phase files). A `conflict` means a
   hand-written phase file is still there: back to 2 (`--force` replaces it once its work lives in a part).

## 2. Per app

Go through the apps one by one (skip libs: they are covered through the apps and workspaces that build them).
For each, find out before asking, from the app's files, its README and the repo's CLAUDE.md/INTENT.md:

- **how it is checked**: its test, lint, format and build commands, and how long they take (run them once: a gate
  that takes minutes still belongs in `worktree-pre-merge` when nothing cheaper covers it, but say so);
- **how it is delivered**: installed from the main checkout (`cargo install --path`, an app bundle, a
  launchd service), run straight from the main checkout (nothing to do), or published elsewhere (never publish
  from a hook without the user asking for it);
- **what it shares**: a workspace whose checks cover several apps at once becomes one part of its own
  (`rust-workspace`), checked once instead of once per app.

Then propose the app's parts in one question per app: what each phase would run and when (its `paths`), with the
recommended set first; the reference's recipes are the defaults per stack. Typical:

| Phase | For | Examples |
|---|---|---|
| `worktree-pre-merge` | gates: the landing stops when they fail, main untouched | tests, lint, format check, a debug build |
| `main-pre-commit` | changes that belong in the merge commit | version bump, a generated file, a changelog entry |
| `main-post-commit` | delivery after the landing (a failure only warns) | install the CLI, rebuild and restart the app |

Write the chosen parts: `paths` with the app's files and the crates or libs it builds from, `**/*.md` excluded
unless docs feed the build; scripts start with `hal_skip_unless_changed` unless they must run on every landing
(say why in a comment, like a self-healing install). Follow the repo's shell style and comment each script's
purpose in its first lines.

## 3. Verify

1. `python3 $H check`: no errors (bad syntax, a missing `paths`, a pathspec that matches nothing) and no warnings
   (an app in no part, a stray file in a part) you cannot explain.
2. Try every new or changed part:
   - `python3 $H try worktree-pre-merge --all-changed --part <parts>`: the gates run for real in this worktree;
     they must pass on the current code and leave `git status` unchanged (a gate that writes files fails the
     landing: gitignore its output).
   - `python3 $H try main-pre-commit --all-changed --part <parts>`: runs in a throwaway worktree of the default
     branch with this branch merged in (removed afterwards); check what it changed in its output.
   - `main-post-commit` does what a landing does (installs, restarts) from the throwaway worktree: ask before
     `python3 $H try main-post-commit --yes --part <parts>`, and skip parts whose result depends on the checkout's
     path or name (an app named after its worktree); their first real landing is the test.
   - Without `--all-changed`, try shows the change detection: commit first, then only parts whose `paths` the
     branch touched run.
3. Commit the hooks (`.hal/hooks/` is tracked) with a message in the repo's style.

## 4. Report

A table of the apps and their parts (phase, what it runs, when), what `try` ran and its result, what was not
tried and why, and anything left open (an app without a gate, a slow gate).

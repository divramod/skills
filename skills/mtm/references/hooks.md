# merge-to-main hooks: reference

What `/mtm config` builds and what `/mtm` and `/mfm` run. The rules are hal2's
[declarative-hooks ADR](https://github.com/divramod/hal2/blob/main/.adr/declarative-hooks.md) (per-app verb scripts, settings in
`.hal/hooks.toml`) and [merge-hooks ADR](https://github.com/divramod/hal2/blob/main/.adr/merge-hooks.md) (the phase
scripts that stay as escape hatch); this file adds the commands, default scripts per stack and hal2's own configuration as example.

## The files

| File | Tracked | Holds |
|---|---|---|
| `<row>/.hal/hooks/<verb>.sh` | yes | a row's own task for a verb (a workspace's: `<workspace path>/.hal/hooks/<verb>.sh`) |
| `code/<lang>/.hal/hooks/{apps,libs}/<verb>.sh` | yes | the inherited default for every app or lib of that language without its own script |
| `code/<lang>/scripts/<name>/main.<ext>` | yes | parametrized helpers the one-line row scripts call (a version bump, a signing step) |
| `.hal/hooks.toml` | yes | `jobs`, custom verbs, row settings (`paths`, `needs`, `lock`, `ignore`), task settings and switches |
| `.hal/hooks.machine.toml` | no (gitignored, main checkout only) | `enabled = true/false` per task and `jobs`, for this machine |
| `.hal/hooks/<flow>/<phase>.sh` | yes | optional phase scripts for what no task can say; run after the phase's tasks |

A task is a script, run as `bash <script>` from the row's folder: the row's own `<row>/.hal/hooks/<verb>.sh`,
else the default of its language and section. A workspace's own scripts are not inherited by its members. No
script, no task: never write `exit 0` stubs; a row opts out of an inherited default with `enabled = false`.
Scripts start with `#!/usr/bin/env bash` and `set -euo pipefail`, are executable and named after a verb.

```toml
version = 2
jobs = 4                             # optional: tasks at once (default max(2, cores/2))

[verbs.docs]                         # a custom verb, or an override of a built-in
phase = "worktree-pre-merge"         # required for a new verb
needs = ["build"]                    # verbs of the same row that must pass first
lock = "net"
ignore = ["*.png"]

[workspaces.rust]                    # its scripts live in code/rust/.hal/hooks/
path = "code/rust"

[apps.hal2-macos]                    # a row: code/<lang>/apps/<name>
paths = ["code/swift/libs"]          # extra files it is built from
needs = ["rust", "Hal2Kit"]          # rows whose same verb must pass first
lock = "xcode"                       # tasks with the same lock never overlap

[apps.hal2-uniffi-bindgen.install]   # one task's settings; only these keys
enabled = false                      # opts out of the inherited install
# paths, ignore = ["**/tests/**"], timeout = "10m", lock
```

Rows come from the filesystem (`code/<lang>/{apps,libs}/<name>` and the workspaces, libs a workspace covers
included); a row needs no `hooks.toml` entry to have tasks. A row's files are its folder and its script, for
Rust rows also their cargo path dependencies, plus its `paths`; `**/*.md` never counts. `cargo:<package>` in
`paths` stands for a workspace crate: its folder, its path dependencies' folders, the workspace `Cargo.toml` and
only the `Cargo.lock` entries of its dependency closure (a lockfile change elsewhere does not count). A task's own `paths`
replace the row's; `ignore` is the task's, else the row's, else the verb's. `check` (and every landing) fails on
an unknown key or section, a `run` or `cwd` key, `version` other than 2, a script named after no verb, a script
not executable or without `#!`, a settings table no script resolves for, an unknown row in `needs` or a cycle,
so a typo never silently changes what runs.

## Verbs and phases

| Verb | Phase | Needs (same row) | Runs when |
|---|---|---|---|
| setup | `setup`: after `/mfm`, on a new worktree slot, before a landing's gates (worktree), after a landing (main) | | the row's manifests + lockfiles changed since its last setup in that checkout |
| lint | `worktree-pre-merge`: in the worktree, after the default branch was merged in, before the merge lock; checks formatting too, never writes | | the branch changed the row (`merge-base..HEAD`) and its inputs did not pass before (else `cached`) |
| build | `worktree-pre-merge` | | same |
| test-unit | `worktree-pre-merge` | build | same |
| test-e2e | `worktree-pre-merge` | test-unit | same |
| version | `main-pre-commit`: on the staged merge in the main checkout; its edits go into the merge commit (lock `repo`) | | the staged merge changes the row |
| install | `main-post-commit`: after the merge commit was pushed and the lock released, in the delivery worktree `<base>/.deliver` | | the row changed since the task's delivery stamp (no stamp: changed) |
| deploy | `main-post-commit` | install | same |

version, install and deploy ignore `**/tests/**`, `**/Tests/**`, `**/UITests/**` by default: a test-only change
never bumps or redelivers. A repo adds verbs (or overrides a built-in's `needs`/`lock`/`ignore`) under
`[verbs.<name>]`.

- A landing: setup and gates in the worktree without a lock; then a ticket in the repo's **merge queue**
  (`~/.hal/git/worktree/<repo>/.merge-queue/`, first come first served, no timeout; `hal2-cli-git worktree
  queue`); under the merge lock the main checkout is fast-forwarded, and when the default branch moved since the
  gates it is merged into the worktree again and the gates rerun (the cache skips unchanged ones); then merge,
  version, commit, push, and the lock is released. The deliveries run afterwards in the **delivery worktree**
  `<base>/.deliver` (detached, warm build caches, its own lock) on the newest default branch commit, so queued
  landings coalesce into one delivery; builds there are named as main's (`HAL2_BUILD_AS_MAIN=1`).
  `hal2-cli-git worktree deliver` runs the deliveries alone.
- Every landing writes a **landing record** as it goes (steps with their times, every planned task with its
  `needs`, lock wait and hold, queue position): `hal2-cli-hooks landings [<id>] [--json]`, the Landings part of
  the Hooks tab (list, timeline, DAG, table) and hal2-macos's Merge Queue pane.
- Phases run one after the other (setup, gates, version, install/deploy), each followed by its phase script.
  **Inside a phase the tasks run as a graph, in parallel** (up to `jobs`): a task waits for the verbs it needs in
  its row and for the same verb of the rows its row `needs` (a workspace's members need the workspace); tasks
  with the same `lock` never overlap (`simulator` for what uses the iOS simulator, `repo` for anything that writes
  the checkout). With more than one task running, each output line is prefixed `<row> <verb> │ `.
- A failing setup, gate or version task stops the landing (exit 4, `status: "task_failed"` with `phase`, `row`,
  `kind` (the verb), `exit_code`, `output`): the phase's running tasks end `cancelled`, the unstarted ones
  `skipped`; main stays untouched, a failed version task aborts the merge. A failing install or deploy only
  warns and skips the tasks that need it; the landing stays.
- A setup or gate phase in a worktree that changes `git status` fails every task that passed in it
  (`left_changes`): gates must not write tracked or unignored files (gitignore build output).
- **Gate result cache**: a gate that counts as changed but passed before with identical inputs (script,
  input file blobs, `Cargo.lock` closure, toolchain versions) ends `cached` instead of running; one cache per repo
  on the machine, shared by its worktrees. `run --phase` uses it unless `--no-cache` or `--all`;
  `hal2-cli-hooks cache list|clear`.
- A **delivery stamp** is the commit an install or deploy last delivered successfully from a clean main checkout
  on this machine (`~/.local/state/hal2/hooks/`). A failed or never-run delivery reruns on the next landing, an
  unchanged one is skipped. `hal2-cli-hooks stamp <row> install` shows it, `--set <commit>` records one (after
  installing by hand, or when migrating hooks whose installs are already current).
- Scripts run in the login-shell environment with `HAL_HOOK_WORKTREE`, `HAL_HOOK_BRANCH`, `HAL_HOOK_MAIN_ROOT`,
  `HAL_HOOK_DEFAULT_BRANCH`, `HAL_APP` (the row key), `HAL_APP_DIR` (its folder, relative to the checkout root),
  `HAL_TASK` (the verb), `HAL_PHASE`; a Cargo workspace's tasks also `HAL_CHANGED_PACKAGES` (the members the range
  affects plus their reverse dependencies; unset for `--all`: cover the whole workspace), so a workspace's lint
  and tests can run `-p` per affected crate. Every outcome (`passed`, `failed`, `timed-out`, `cancelled`, `skipped`,
  `unchanged`, `cached`, `disabled` with its layer) is in the merges' `--json` under `tasks` (each with `row` and `kind`,
  the verb). Run records (last 20 per checkout and task, with logs) carry a trigger: `landing`, `merge` or
  `manual`.

## hal2-cli-hooks

`hal2-cli-hooks <command> [--json] [--repo <dir>]`, from the checkout whose scripts and `hooks.toml` it edits (a
worktree; `--machine` always edits the main checkout's machine layer). `<row>` is `apps.<name>`, `libs.<name>`,
`workspaces.<name>` or a unique name; `<verb>` a built-in or one of the repo's `[verbs.<name>]`.

| Command | Does |
|---|---|
| `list` | rows (configured and discovered) with their tasks, scripts (own or inherited, with the path), switches and last runs |
| `suggest [--write]` | suggested scripts per stack; `--write` writes the missing ones as the rows' own scripts (install off) |
| `set <row> <verb> [--run <cmd>] [--paths a,b] [--ignore a,b] [--timeout 10m] [--lock <name>]` | `--run` writes the row's own script (shebang, `set -euo pipefail`, the command, `chmod +x`); the rest are the task's settings |
| `remove <row> <verb>` | delete the row's own script and its settings |
| `enable`, `disable <row> <verb> [--machine]` | switch a task (also an inherited one) in `hooks.toml`, or only on this machine |
| `reset <row> <verb>` | drop this machine's switch |
| `gates <workspace> per-app\|workspace` | move a workspace's gate scripts to its apps, or back |
| `check` | validate both files, the scripts and the row folders |
| `run <row> <verb>` | run one task now, changed or not, without its needs |
| `run --phase <phase> [--all] [--base <ref>] [--dry-run] [--no-cache]` | run a phase the way a landing does (`--all`: every row counts as changed); `--dry-run` lists what would run and why (changed paths, lockfile closure, unchanged, cached, off, no stamp) without running |
| `cache list\|clear` | the gate result cache's entries |
| `landings [<id>] [--limit <n>]` | the landing records, newest first; one with its steps and tasks |
| `stamp <row> <verb> [--set <commit>]` | show or record a delivery stamp |
| `commit [--message]` | commit `.hal/hooks.toml` on the default branch of the main checkout and push |

## Default scripts per stack

`suggest` proposes these commands; adapt them to what the repo's README, CLAUDE.md or CI actually run. When
several rows of a language would get the same script, write it once as the language default
(`code/<lang>/.hal/hooks/{apps,libs}/<verb>.sh`, using `$HAL_APP`/`$HAL_APP_DIR`) instead of per row; logic that
differs only in arguments goes into a helper under `code/<lang>/scripts/<name>/main.<ext>`.

| Stack | setup | lint | build / test-unit | install |
|---|---|---|---|---|
| Cargo workspace (scripts on the `workspaces.<name>` row) | `cargo fetch --locked` | `cargo fmt --all --check`, `cargo clippy --all-targets --locked -- -D warnings` (`-p` per `$HAL_CHANGED_PACKAGES` when set) | no build gate (clippy and the tests compile); `cargo nextest run --locked` + `cargo test --doc` (same `-p`), `cargo test --locked` without nextest | apps default: `cargo install --locked --quiet --path "$HAL_APP_DIR"` (from the checkout root) |
| bun / npm / pnpm | `bun install --frozen-lockfile` (`npm ci`, `pnpm i --frozen-lockfile`) | the package's `lint` script | its `build`, `test` scripts | a global CLI: `bun link` / `npm i -g .`; run from the checkout: none |
| SwiftPM library | `xcrun swift package resolve` | `xcrun swift-format lint --strict --recursive .` | `xcrun swift build`; `xcrun swift test` | none: apps that link it rebuild |
| Xcode / XcodeGen app | | | the repo's build script (`./build.sh build`; `./build.sh`); test-e2e: UI tests | release build into `~/Applications`; deploy: restart |
| Neovim plugin (plenary) | | `stylua --check .` (with a stylua.toml) | test-unit: `nvim --headless -u tests/minimal_init.lua -c "PlenaryBustedDirectory tests/ {...}" -c qa!` | none when lazy.nvim loads it with `dir =` from the main checkout |
| Python (uv) | `uv sync --locked` | `uv run ruff format --check`, `uv run ruff check` | test-unit: `uv run pytest` | a tool: `uv tool install --force .` |
| Go | `go mod download` | `test -z "$(gofmt -l .)"`, `go vet ./...` | test-unit: `go test ./...` | `go install ./...` |

- `version` fits whatever must be part of the landed commit: a version bump, regenerated code, a changelog line.
  Keep it deterministic.
- Gate before landing, never after: a post-phase failure no longer stops anything. Split what is slow into
  `test-e2e`, so it starts only after `test-unit` passed.
- Delivery only installs locally; publishing (a release, a registry push, a remote deploy) needs the user's
  explicit wish. `deploy` is never suggested.
- A row's `paths` must hold everything the app is **built from** that is not its folder or a cargo dependency:
  shared Swift libs, build scripts, assets, a web page it bundles; its `needs` the rows whose same verb must pass
  first (the libs it links).

## hal2's configuration

hal2 (`~/a/hal2`, `github.com/divramod/hal2`) has a Rust workspace of CLIs and libs, Swift packages, a macOS and
an iOS app linking the Rust core, two bun apps and a Neovim plugin; its
[`.hal/hooks.toml`](https://github.com/divramod/hal2/blob/main/.hal/hooks.toml) and scripts:

| Row | Own scripts | Inherited | hooks.toml |
|---|---|---|---|
| `workspaces.rust` | `code/rust/.hal/hooks/`: lint (fmt of all, clippy `-D warnings` of `HAL_CHANGED_PACKAGES`), test-unit (nextest + doctests of the same); no build | | `path` |
| rust apps (`hal2-cli*`, `hal2-api`, ...) | hal2-api: deploy (`hal2-api install`, waits until healthy) | install from `code/rust/.hal/hooks/apps/` (`cargo install` + `code/bash/scripts/codesign-dev`), tests ignored | `hal2-uniffi-bindgen.install` off |
| `libs.Hal2Kit` | test-unit (macOS + iOS simulator `hal2-<worktree>`, against a real hal2-api) | | `lock = "simulator"`, `paths` (`cargo:hal2-api`) |
| `libs.Hal2Core` | test-unit (build-core, then `swift test`) | | `needs = ["rust"]`, `paths` (`cargo:hal2-ffi`, ...) |
| `apps.hal2-macos` | install (`build.sh install`), deploy (restart) | test-unit (`build.sh`, no separate build), version (`bump-xcodegen-version`) from `code/swift/.hal/hooks/apps/` | `needs` rust, Hal2Kit, Hal2Core, hal2-excalidraw, hal2-mermaid; no lock (runs beside the simulator lane); `paths` |
| `apps.hal2-ios` | install (`build.sh ota`), test-e2e | test-unit, version | `needs` Hal2Kit, hal2-excalidraw; `lock = "simulator"`; `paths`, the install its own `paths` |
| `apps.hal2-statusline`, `apps.hal2-excalidraw`, `apps.hal2-mermaid` | the pages: build (`bun run build`) | setup, lint, test-unit from `code/typescript/.hal/hooks/apps/` | (run from the checkout / bundled by hal2-macos) |
| `apps.hal2-nvim` | test-unit (plenary specs) | | (lazy.nvim `dir =` the checkout) |

## Migrating script hooks

A repo with `.hal/hooks/merge-to-main/<phase>.sh` scripts (hand-written, or shot 4's managed `lib.sh` +
`parts/<part>/`), or a version-1 `hooks.toml` with `run`/`cwd` per task: per command, find the row it belongs to
and the verb it does and move it into that row's script (`hal2-cli-hooks set <row> <verb> --run <cmd>`), or into
the language default when several rows share it; a formatting check joins `lint`, a `test` splits into
`test-unit` and `test-e2e`. Its change detection becomes the row's `paths`, `needs` and the task's `ignore`, then
set `version = 2`. Deliveries that are current already get a stamp (`hal2-cli-hooks stamp <row> install --set
<commit the installed build came from>`), so the first landing on the new config does not reinstall everything.
`git rm` the old scripts; keep a phase script only for what no task can say. hal2 was migrated this way in plan
0008 step 6 and plan 0010 step 5.

## Rehearsing landings

`run --phase` runs one phase. To test the whole chain (the real `hal2-cli-git`, the merge lock, the push, change
detection across phases, stamps), rehearse in a sandbox clone; its main checkout gets its own lock
(`~/.hal/git/worktree/<name>/`) and its own state dir (keyed by the main checkout's path):

```bash
git clone -q --bare <repo> sbx/origin.git && git clone -q sbx/origin.git sbx/<repo>-sbx
git -C sbx/<repo>-sbx remote set-head origin main && git -C sbx/<repo>-sbx worktree add -q -b wt ../wt
# per scenario: commit a change in sbx/wt, then
(cd sbx/wt && hal2-cli-git worktree merge-to-main --json)
```

Scenarios worth one landing each: a change to one app only (only its tasks run), a change to shared code (every
dependent row's tasks run, version bump, delivery), a test-only change (gates run, no bump, no delivery; one new
test per app also proves each gate runs that app's tests), a failing gate (exit 4, main unchanged; the phase's
other running tasks `cancelled`, the rest `skipped`), a failing
version task (merge aborted, main clean) and a failing install (landed, pushed, a warning; a throwaway row does
both; its deploy ends `skipped`), rows with `needs` (a lib's failing build skips the apps that need it) and two
tasks sharing a `lock` (they never overlap in the prefixed output). Also `/mfm` after a lockfile change (setup reruns) and the first landing after seeding stamps (unchanged
rows deliver nothing). Deliveries from the sandbox are real (installs, restarts): ask first, or point the tasks at
harmless commands with `hal2-cli-hooks set <row> <verb> --run` in the sandbox; the next real landing delivers from the main checkout
again (its stamps are separate). Remove `sbx/` and `~/.hal/git/worktree/<repo>-sbx/` afterwards.

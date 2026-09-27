# merge-to-main hooks: reference

What `/mtm config` builds and what `/mtm` and `/mfm` run. The rules are hal2's
[declarative-hooks ADR](https://github.com/divramod/hal2/blob/main/.adr/declarative-hooks.md) (per-app tasks in
`.hal/hooks.toml`) and [merge-hooks ADR](https://github.com/divramod/hal2/blob/main/.adr/merge-hooks.md) (the phase
scripts that stay as escape hatch); this file adds the commands, recipes and hal2's own configuration as example.

## The files

| File | Tracked | Holds |
|---|---|---|
| `.hal/hooks.toml` | yes | one row per app, lib or shared workspace, one task per kind |
| `.hal/hooks.machine.toml` | no (gitignored, main checkout only) | `enabled = true/false` per task, for this machine |
| `.hal/hooks/<flow>/<phase>.sh` | yes | optional scripts for what a command line can't say; run after the phase's tasks |
| `.hal/hooks/scripts/*.sh` | yes | helper scripts a task's `run` calls (a version bump) |

```toml
version = 1

[workspaces.rust]                    # checks shared by every crate
path = "code/rust"
format = { run = "cargo fmt --all --check", cwd = "code/rust" }

[apps.hal2-macos]                    # a row: code/<lang>/apps/<name>
paths = ["code/swift/libs"]          # extra files it is built from

[apps.hal2-macos.version]            # one task per kind
run = ".hal/hooks/scripts/hal2-macos-bump.sh"
cwd = "."                            # relative to the checkout root (default)
ignore = ["**/Tests/**"]             # never counts as a change
timeout = "10m"                      # optional
enabled = true                       # default
```

A row's files are its folder, for Rust apps and libs also the crates they depend on (`cargo metadata`) and the
workspace's `Cargo.toml`/`Cargo.lock`, plus its `paths`; `**/*.md` never counts. A task's own `paths` replace the
row's. An unknown key, kind or section fails `check` and the landing, so a typo never silently disables a gate.

## Kinds and phases

| Kind | Runs | Runs when |
|---|---|---|
| setup | after `/mfm`, on a new worktree slot, before a landing's gates (worktree), after a landing (main) | the row's manifests + lockfiles changed since its last setup in that checkout |
| format, lint, build, test | `worktree-pre-merge`: in the worktree, after the default branch was merged in | the branch changed the row (`merge-base..HEAD`) |
| version | `main-pre-commit`: on the staged merge in the main checkout; its edits go into the merge commit | the staged merge changes the row |
| install, deploy | `main-post-commit`: after the merge commit was pushed | the row changed since the task's delivery stamp (no stamp: changed) |

- A phase runs its kinds in this order, each kind across all rows (every format, then every lint, ...), then the
  phase's script when there is one.
- A failing setup, gate or version task stops the landing (exit 4, `status: "task_failed"` with `phase`, `row`,
  `kind`, `exit_code`, `output`): main stays untouched, a failed version task aborts the merge. A failing
  install or deploy only warns; the landing stays.
- A setup, gate or version task in a worktree that exits 0 but changes `git status` fails too: gates must not
  write tracked or unignored files (gitignore build output).
- A **delivery stamp** is the commit an install or deploy last delivered successfully on this machine
  (`~/.local/state/hal2/hooks/`). A failed or never-run delivery reruns on the next landing, an unchanged one is
  skipped. `hal2-cli-hooks stamp <row> install` shows it, `--set <commit>` records one (after installing by hand,
  or when migrating hooks whose installs are already current).
- Tasks run as `bash -c <run>` from `cwd` in the login-shell environment with `HAL_HOOK_WORKTREE`,
  `HAL_HOOK_BRANCH`, `HAL_HOOK_MAIN_ROOT`, `HAL_HOOK_DEFAULT_BRANCH`, `HAL_APP`, `HAL_APP_DIR`, `HAL_TASK`,
  `HAL_PHASE`. Every outcome (`passed`, `failed`, `unchanged`, `disabled` with its layer, `timed-out`) is in the
  merges' `--json` under `tasks`.

## hal2-cli-hooks

`hal2-cli-hooks <command> [--json] [--repo <dir>]`, from the checkout whose `hooks.toml` it edits (a worktree;
`--machine` always edits the main checkout's machine layer). `<row>` is `apps.<name>`, `libs.<name>`,
`workspaces.<name>` or a unique name.

| Command | Does |
|---|---|
| `list` | rows (configured and discovered) with stacks, tasks, switches and last runs |
| `suggest [--write]` | suggested tasks per stack; `--write` adds the missing ones (installs off) |
| `set <row> <kind> --run <cmd> [--cwd] [--paths a,b] [--ignore a,b] [--timeout 10m]` | create or change a task |
| `remove <row> <kind>` | delete a task |
| `enable`, `disable <row> <kind> [--machine]` | switch a task in `hooks.toml`, or only on this machine |
| `reset <row> <kind>` | drop this machine's switch |
| `gates <workspace> per-app\|workspace` | move a workspace's gates to its apps, or back |
| `check` | validate both files, row folders and cwds |
| `run <row> <kind>` | run one task now, changed or not |
| `run --phase <phase> [--all] [--base <ref>]` | run a phase the way a landing does (`--all`: every row counts as changed) |
| `stamp <row> install\|deploy [--set <commit>]` | show or record a delivery stamp |
| `commit [--message]` | commit `.hal/hooks.toml` on the default branch of the main checkout and push |

## Recipes per stack

`suggest` proposes these; adapt them to what the repo's README, CLAUDE.md or CI actually run.

| Stack | setup | gates | install |
|---|---|---|---|
| Cargo workspace (one `workspaces.<name>` row) | `cargo fetch --locked` | `cargo fmt --all --check`, `cargo clippy --all-targets --locked -- -D warnings`, `cargo test --locked` | per binary: `cargo install --locked --quiet --path apps/<app>` (cwd the workspace), `ignore = ["**/tests/**"]` |
| bun / npm / pnpm | `bun install --frozen-lockfile` (`npm ci`, `pnpm i --frozen-lockfile`) | the package's `lint`, `build`, `test` scripts | a global CLI: `bun link` / `npm i -g .`; run from the checkout: none |
| SwiftPM library | `xcrun swift package resolve` | `xcrun swift build`, `xcrun swift test` | none: apps that link it rebuild |
| Xcode / XcodeGen app | | the repo's build script with tests (`build.sh`) | build release into `~/Applications`; deploy: restart |
| Neovim plugin (plenary) | | `stylua --check .` (with a stylua.toml), `nvim --headless -u tests/minimal_init.lua -c "PlenaryBustedDirectory tests/ {...}" -c qa!` | none when lazy.nvim loads it with `dir =` from the main checkout |
| Python (uv) | `uv sync --locked` | `uv run ruff format --check`, `uv run ruff check`, `uv run pytest` | a tool: `uv tool install --force .` |
| Go | `go mod download` | `test -z "$(gofmt -l .)"`, `go vet ./...`, `go test ./...` | `go install ./...` |

- `version` fits whatever must be part of the landed commit: a version bump, regenerated code, a changelog line.
  Keep it deterministic; put it in a script under `.hal/hooks/scripts/` and point `run` at it.
- Gate before landing, never after: a post-phase failure no longer stops anything.
- Delivery only installs locally; publishing (a release, a registry push, a remote deploy) needs the user's
  explicit wish. `deploy` is never suggested.
- A row's `paths` must hold everything the app is **built from** that is not its folder or a cargo dependency:
  shared Swift libs, build scripts, assets, a web page it bundles.

## hal2's configuration

hal2 (`~/a/hal2`, `github.com/divramod/hal2`) has Rust CLIs, a SwiftUI app linking the Rust core and bundling a web
page, two bun apps and a Neovim plugin; its [`.hal/hooks.toml`](https://github.com/divramod/hal2/blob/main/.hal/hooks.toml):

| Row | setup | gates | version | install / deploy |
|---|---|---|---|---|
| `workspaces.rust` | | fmt, clippy `-D warnings`, test | | |
| `apps.hal2-cli`, `-cli-git`, `-cli-hooks`, `-cli-shooter`, `-cli-tmux` | | (the workspace's) | | `cargo install --path`, tests ignored |
| `apps.hal2-macos` (+ Swift libs and scripts, Rust libs, bindgen, the Excalidraw page, logos) | | `build.sh` (debug build + Hal2Kit and app tests) | `.hal/hooks/scripts/hal2-macos-bump.sh` | `build.sh install`; deploy: `.hal/hooks/scripts/hal2-macos-restart.sh` |
| `apps.hal2-statusline`, `apps.hal2-excalidraw` | `bun install --frozen-lockfile` | `bun run lint`, `bun run test` | | (run from the checkout / bundled by hal2-macos) |
| `apps.hal2-nvim` | | plenary specs | | (lazy.nvim `dir =` the checkout) |

## Migrating script hooks

A repo with `.hal/hooks/merge-to-main/<phase>.sh` scripts (hand-written, or shot 4's managed `lib.sh` +
`parts/<part>/`): per script, find the row it belongs to and the kind it does, and turn it into a task
(`hal2-cli-hooks set`); its change detection becomes the row's `paths` and the task's `ignore`, a script body
that is more than a command line moves to `.hal/hooks/scripts/`. Deliveries that are current already get a
stamp (`hal2-cli-hooks stamp <row> install --set <commit the installed build came from>`), so the first landing
on the new config does not reinstall everything. `git rm` the old scripts; keep a phase script only for what no
task can say. hal2 was migrated this way in plan 0008 step 6.

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
test per app also proves each gate runs that app's tests), a failing gate (exit 4, main unchanged), a failing
version task (merge aborted, main clean) and a failing install (landed, pushed, a warning; a throwaway row does
both). Also `/mfm` after a lockfile change (setup reruns) and the first landing after seeding stamps (unchanged
rows deliver nothing). Deliveries from the sandbox are real (installs, restarts): ask first, or point the tasks at
harmless commands with `hal2-cli-hooks set` in the sandbox; the next real landing delivers from the main checkout
again (its stamps are separate). Remove `sbx/` and `~/.hal/git/worktree/<repo>-sbx/` afterwards.

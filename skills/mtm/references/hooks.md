# merge-to-main hooks: reference

What `/mtm config` builds and what `/mtm` runs. The contract of the hooks themselves is hal2's
[merge-hooks ADR](https://github.com/divramod/hal2/blob/main/.adr/merge-hooks.md); this file adds the managed
per-part layout on top of it, the helpers and worked examples from hal2.

## The phases

`hal2-cli-git worktree merge-to-main` runs these scripts with `bash` when they exist, from the copy in the merged
tree (a branch that changes a hook uses it in the same landing), with `HAL_HOOK_WORKTREE`, `HAL_HOOK_BRANCH`,
`HAL_HOOK_MAIN_ROOT` and `HAL_HOOK_DEFAULT_BRANCH` set:

| Phase | Runs in | When | Failure |
|---|---|---|---|
| `worktree-pre-merge` | the worktree | after the default branch was merged in | landing stops, main untouched |
| `main-pre-commit` | the main checkout | after `git merge --no-ff --no-commit`; changed files go into the merge commit | merge aborted, main unchanged |
| `main-post-commit` | the main checkout | after the merge commit was made and pushed | warning only, the landing stays |

A pre phase that exits 0 but leaves `git status` changed in the worktree fails too: gates must not write tracked
or unignored files.

## The managed layout

```
.hal/hooks/merge-to-main/
  lib.sh                      dispatcher + helpers (managed: hooks.py init writes and updates it)
  worktree-pre-merge.sh       managed: `source lib.sh; hal_run_parts worktree-pre-merge`
  main-pre-commit.sh          managed
  main-post-commit.sh         managed
  parts/<part>/
    paths                     the part's files: one git pathspec per line, `#` comments
    worktree-pre-merge.sh     any of the three phases, all optional
    main-pre-commit.sh
    main-post-commit.sh
```

- A **part** is one app (`hal2-macos`) or one workspace several apps share (`rust-workspace`: fmt, clippy and
  tests run once for every crate). Parts run in name order.
- A part script is **sourced** by `bash -euo pipefail` from the root of the checkout the phase runs in, with
  `HAL_PHASE`, `HAL_PART` and `HAL_PART_DIR` set and the helpers loaded; no shebang or `set` line needed. `exit 0`
  ends the part.
- A failing part stops `worktree-pre-merge` and `main-pre-commit` at once; in `main-post-commit` the other parts
  still run and the phase fails at the end.
- `HAL_HOOK_FORCE_CHANGED=1` counts every part as changed, `HAL_HOOK_ONLY_PART=a,b` runs only those parts
  (`hooks.py try` sets them). Written for bash 3.2 too (macOS's `/bin/bash`).

### Helpers

| Helper | Does |
|---|---|
| `hal_skip_unless_changed [<pathspec>...]` | print "unchanged, skipped" and exit 0 unless the part's files changed |
| `hal_changed [<pathspec>...]` | status 0 when the part's files changed in this landing |
| `hal_changed_since <commit> [<pathspec>...]` | ... since `<commit>` (an unknown commit counts as changed) |
| `hal_log <message>` | print `<phase>[<part>]: <message>` |

"Changed" per phase: the branch's own changes (`git diff $(git merge-base HEAD origin/<default>) HEAD`) in
`worktree-pre-merge`, the staged merge (`git diff --cached HEAD`) in `main-pre-commit`, the merge commit
(`git diff HEAD^1 HEAD`) in `main-post-commit`. Extra pathspecs narrow the part's files for one check, e.g. tests
aside: `hal_changed ':(exclude,glob)**/Tests/**'`. A git error counts as changed: a check rather runs once too
often than never.

### Paths

```
# The files hal2-macos is built and tested from.
:(glob)code/swift/apps/hal2-macos/**
:(glob)code/rust/libs/**           # a crate the app links
code/rust/Cargo.lock
:(exclude,glob)**/*.md             # docs never trigger a check
```

Include what the app is **built from**, not only its own folder: its libs, the workspace manifest and lockfile,
shared build scripts and assets. `hooks.py check` fails on a pathspec that matches no tracked file (a typo) and
warns about an app no part covers.

## Recipes per stack

Defaults to propose; adapt the commands to what the repo's README, CLAUDE.md or CI actually run.

| Stack | `worktree-pre-merge` | `main-post-commit` |
|---|---|---|
| Cargo workspace (one part for the workspace) | `cargo fmt --all --check`, `cargo clippy --all-targets --locked -- -D warnings`, `cargo test --locked` | per installed binary (one part per app): `cargo install --locked --quiet --path apps/<app>` |
| bun / npm / pnpm | `bun install --frozen-lockfile` (`npm ci`, `pnpm i --frozen-lockfile`), then the package's `test`, `lint`, `typecheck`, `build` scripts | a global CLI: `bun link` / `npm i -g .`; run from the checkout: nothing |
| SwiftPM library | `xcrun swift test --package-path <dir>` | nothing: apps that link it rebuild |
| Xcode / XcodeGen app | the repo's build script with tests (`build.sh`), or `xcodebuild test` | build release, install to `~/Applications`, restart (see hal2-macos) |
| Neovim plugin (plenary) | `nvim --headless -u tests/minimal_init.lua -c "PlenaryBustedDirectory tests/ {...}" -c qa!` | nothing when lazy.nvim loads it with `dir =` from the main checkout |
| Python (uv) | `uv run ruff check`, `uv run ruff format --check`, `uv run pytest` | a tool: `uv tool install --force .` |
| Go | `test -z "$(gofmt -l .)"`, `go vet ./...`, `go test ./...` | `go install ./cmd/<app>` |

`main-pre-commit` fits whatever must be part of the landed commit: a version bump, regenerated code or schema, a
changelog line. Keep its edits deterministic: it runs on the staged merge in the main checkout.

Rules of thumb:

- Gate in `worktree-pre-merge`, never in `main-post-commit`: a post failure no longer stops anything.
- Skip unless changed, except where re-running is cheap and repairs drift (an install that cargo makes a no-op when
  nothing changed): say so in the script's comment.
- Delivery from a hook only installs locally; publishing (a release, a registry push, a deploy) needs the user's
  explicit wish.
- Output of gates (build folders, `node_modules`) must be gitignored, or the pre phase fails for leaving changes.

## Worked examples: hal2

hal2 (`~/a/hal2`, `github.com/divramod/hal2`) has Rust CLIs, a SwiftUI app linking the Rust core, a bun
statusline and a Neovim plugin:

| Part | `paths` | `worktree-pre-merge` | `main-pre-commit` | `main-post-commit` |
|---|---|---|---|---|
| `rust-workspace` | `code/rust/**` | fmt, clippy `-D warnings`, test | | |
| `hal2-cli`, `hal2-cli-git`, `hal2-cli-shooter`, `hal2-cli-tmux` | the app + its libs + Cargo.toml/lock | | | `cargo install --path` (always) |
| `hal2-macos` | swift app, Hal2Kit, swift scripts, rust libs, bindgen, logos | `build.sh` (debug build + tests) | bump patch version + build number | rebuild, install, restart when changed since the installed build |
| `hal2-statusline` | the app | bun install, test, biome | | (runs from the checkout) |
| `hal2-nvim` | the app | plenary specs | | (lazy.nvim `dir =` the checkout) |

`parts/hal2-macos/main-pre-commit.sh`: a change that goes into the merge commit, tests aside:

```bash
# Before the merge commit on main: bump hal2-macos's patch version (and build
# number) when the landing changes the app's code, tests aside; the change
# goes into the merge commit.
spec="code/swift/apps/hal2-macos/project.yml"
hal_skip_unless_changed ':(exclude,glob)**/Tests/**' ':(exclude,glob)code/rust/**/tests/**'

version="$(sed -nE 's/^ *CFBundleShortVersionString: "([0-9]+\.[0-9]+\.[0-9]+)"$/\1/p' "$spec")"
build="$(sed -nE 's/^ *CFBundleVersion: "([0-9]+)"$/\1/p' "$spec")"
if [[ -z "$version" || -z "$build" ]]; then
  hal_log "no CFBundleShortVersionString/CFBundleVersion in $spec" >&2
  exit 1
fi
IFS=. read -r major minor patch <<<"$version"
next="$major.$minor.$((patch + 1))"
sed -i '' -E \
  -e "s/^( *CFBundleShortVersionString: )\"$version\"$/\1\"$next\"/" \
  -e "s/^( *CFBundleVersion: )\"$build\"$/\1\"$((build + 1))\"/" \
  "$spec"
hal_log "$version ($build) -> $next ($((build + 1)))"
```

`parts/hal2-macos/main-post-commit.sh`: delivery keyed to what the installed build was built from, not to the
last merge, so a failed rebuild is retried by the next landing:

```bash
app="$HOME/Applications/hal2-macos.app"
# build.sh stamps the commit it built from into Info.plist ("-dirty" counts as unknown).
built="$(/usr/libexec/PlistBuddy -c "Print HAL2Commit" "$app/Contents/Info.plist" 2>/dev/null || true)"
if [[ -n "$built" && "$built" != *-dirty ]] &&
   ! hal_changed_since "$built" ':(exclude,glob)**/Tests/**' ':(exclude,glob)code/rust/**/tests/**'; then
  hal_log "code unchanged since $built, not rebuilt"
  pgrep -x hal2-macos >/dev/null || open "$app"
  exit 0
fi
code/swift/apps/hal2-macos/build.sh install
if pkill -x hal2-macos; then
  while pgrep -x hal2-macos >/dev/null; do sleep 0.2; done
fi
open "$app"
hal_log "restarted $app"
```

`parts/hal2-cli-git/main-post-commit.sh`: an install that runs on every landing on purpose:

```bash
# Not skipped when unchanged: cargo rebuilds only what changed (well under a
# second when nothing did) and this repairs a failed install or one made from
# a worktree.
cd code/rust
cargo install --locked --quiet --path apps/hal2-cli-git
hal_log "installed $(command -v hal2-cli-git || echo hal2-cli-git)"
```

`parts/rust-workspace/worktree-pre-merge.sh`: one gate for every crate:

```bash
hal_skip_unless_changed
cd code/rust
cargo fmt --all --check
cargo clippy --all-targets --locked --quiet -- -D warnings
cargo test --locked --quiet
```

## Migrating hand-written hooks

A repo with its own `.hal/hooks/merge-to-main/<phase>.sh` (no `managed by /mtm config` line): per hook, pick the
part it belongs to, move its path list into `parts/<part>/paths` and its body into `parts/<part>/<phase>.sh`
(drop the shebang, `set -euo pipefail`, `cd "$HAL_HOOK_MAIN_ROOT"`: the dispatcher does that; replace its own
change detection with the helpers), `git rm` the old file, then `hooks.py init`. hal2's hooks were migrated this
way: `hal2-macos-paths.sh` became `parts/hal2-macos/paths`.

## Trying hooks out

`hooks.py try <phase>` runs a phase the way a landing does: `worktree-pre-merge` in this worktree,
`main-pre-commit`/`main-post-commit` in a throwaway worktree of the default branch with this branch merged in
(and the merge committed for post), overlaid with this worktree's `.hal/hooks/`, so uncommitted hook edits are
tried too. `--all-changed` runs every part, `--part a,b` only those; `main-post-commit` needs `--yes` because it
does real work (installs from the throwaway worktree: the next real landing installs from the main checkout
again). `--keep` keeps the throwaway worktree for a look.

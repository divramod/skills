---
name: cleanup
description: Delete the build artifacts of the current git worktree to free disk space — every git-ignored, untracked build output and generated file (Rust target/, Xcode and SwiftPM build folders, .build/, generated .xcodeproj and xcframeworks, dist/, caches), with `--deps` also the fetched dependencies (node_modules/, .venv/, fetched frameworks). Knows the hal project locations (code/rust/target, code/swift/apps/*/build, code/swift/libs/*/.build, Hal2Core's generated Frameworks and hal2_ffi.swift, code/typescript/apps/*/dist and node_modules, ...) plus generic patterns, shows a table with sizes and how each is rebuilt, and deletes only git-ignored paths that hold no tracked file — never secrets, .env, .hal/, plans/ or shotfiles/. Refuses while a build or test still runs in the worktree. Use when the user says /cleanup, "clean the worktree", "delete build artifacts", "free disk space" or a disk is full. `/cleanup h` shows help.
---

# cleanup

Frees the disk space a worktree's builds use. `S=<skill-dir>/scripts`, `C="python3 $S/cleanup.py"`. The script
decides what counts as an artifact and refuses unsafe paths; this skill chooses, asks and reports.

| Call | Does |
|---|---|
| `/cleanup` | table of the artifacts, ask once, delete the `build` and `generated` ones |
| `/cleanup --deps` | the same, with the `deps` ones (node_modules, fetched frameworks, venvs) |
| `/cleanup -y [--deps]` | delete without asking (the user said so) |
| `/cleanup <path>...` | delete just these (worktree-relative), after the same safety checks |
| `/cleanup list` | only the table, delete nothing |
| `/cleanup h`, `/cleanup help` | print this table and stop |

## What counts

`$C list` takes git's ignored, untracked paths (`git ls-files --others --ignored --exclude-standard --directory`),
drops the protected ones and gives each a kind:

- `build`: build output and caches, rebuilt by the next build (`target/`, `build/`, `.build/`, `dist/`,
  `DerivedData`, `*.xcresult`, `*.noindex`, `__pycache__/`, `.pytest_cache/`, `.gradle/`, `.next/`, `.turbo/`, ...).
- `generated`: files a script generates (a generated `.xcodeproj`, an xcframework, bindings).
- `deps`: fetched dependencies; deleting them means a reinstall or download (`node_modules/`, `.venv/`, `Pods/`,
  fetched frameworks). Only with `--deps`.
- `unknown`: ignored but not a known artifact (local notes, a personal config). Never deleted in bulk; name it
  explicitly when the user wants it gone.

Protected, never listed or deleted: `.git`, `.hal/` (worktree runtime state), `.secrets/`, `.env*`, `plans/`
(`CURRENT_PLAN`), `shotfiles/`, `*.machine.toml`. `delete` also refuses a path that is not git-ignored, holds a
tracked file, lies outside the worktree or does not exist.

### hal projects

[`scripts/locations.tsv`](scripts/locations.tsv) names the known locations of hal projects (hal2 and repos with
its layout) with kind and the command that rebuilds each. Seen in hal2's
worktree `01` (2026-09-28, 163 GB in total):

| Location | Kind | Size seen | Rebuilt by |
|---|---|---|---|
| `code/rust/target` | build | 147 GB | `cargo build` |
| `code/swift/apps/{hal2-ios,hal2-macos}/build` | build | 4.3 + 3.6 GB | the app's `build.sh` |
| `code/swift/libs/{Hal2Kit,Hal2Core}/.build`, `.swiftpm` | build | 3.0 + 1.3 GB | `xcrun swift test --package-path ...` |
| `code/swift/build` (iOS DerivedData, xcresult) | build | 2.5 GB | `code/bash/scripts/test-kit-ios/main.sh` |
| `code/swift/libs/Hal2Core/Frameworks`, `Sources/Hal2Ffi/hal2_ffi.swift` | generated | 326 MB | `code/bash/scripts/build-core/main.sh` |
| `code/swift/apps/*/*.xcodeproj`, `Hal2Core/Package.resolved` | generated | < 1 MB | `xcodegen` via `build.sh` |
| `code/typescript/apps/*/dist` | build | 24 MB | `bun run build` |
| `code/typescript/apps/*/node_modules` | deps | 656 MB | `bun install` |
| `code/swift/libs/Hal2Kit/Frameworks` (VLCKit) | deps | 143 MB | `code/bash/scripts/fetch-vlckit/main.sh` |

Outside the worktree and **not** touched: the installed app (`~/Applications/hal2-macos-<worktree>.app`), the
checkout's test simulator (`hal2-<worktree>`), published builds (`~/.local/state/hal2/builds/<app>/<worktree>/`)
and `~/Library/Developer/Xcode/DerivedData`. Mention them when the user wants more space back; delete them only
when asked.

When a hal repo has a new artifact location (a new language, app or generated file), add it to `locations.tsv`
instead of relying on the generic patterns.

## Steps

1. `$C busy` lists the processes whose command line names this worktree (a `cargo`, `xcodebuild`, a hook's
   `test-unit.sh`). When it exits 1, deleting their output breaks them: say which run, and stop (or ask with the
   question tool whether to wait, or clean only paths they don't use). Your own background tasks in this
   worktree count too.
2. `$C list [--deps]` prints the table, largest first, `*` marking what `delete` takes, with the total. Show it
   (or the top rows when it is long) with the total to free. Point out `unknown` rows worth a look.
3. Unless the call says `-y` or names paths, ask once with the question tool: delete the selected ones
   (Recommended), also the deps (`--deps`), or cancel. Anything else the user names goes as explicit paths.
4. `$C delete [--deps]`, or `$C delete <path>...`. It prints `deleted <size> <path>` per path, `skip <path>:
   <why>` for a refused one (exit 1) and the space freed. A large `target/` takes a while: run it in the
   background when the harness allows and say so.
5. Report the space freed, what was skipped and why, and what the next build has to rebuild (the rebuild column;
   in a hal repo e.g. `build-core` before the Swift apps, `bun install` after `--deps`).

Never commit, and never delete tracked files: when a path is tracked but looks like an artifact, report it as a
gitignore candidate instead. If a script exits 2 with a missing-tool error, run `bash $S/install-prerequisites.sh`.

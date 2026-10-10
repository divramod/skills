# hal2 change: a plan's coordinator keeps its model and effort across clears and restarts

This is a brief for a hal2 servant from the skills repository: plan 0015 there, research 0004, decisions D10, D11, D16 and D17. It is self-contained. Paths are relative to `~/a/hal2/code/rust/`, and the line numbers were read on 2026-10-10.

## The problem

The user changed a plan's coordinator session to effort `max`. After a hand-off and clear-and-continue it ran at `medium`. hal2 did that:

- `~/.local/state/hal2/agents/autoclear/10.log` (pane %10, `~/a/dev`, plan `0003-tmux-ghostty-and-alfred-pane-switcher`):
  - `08:35:14 continuing: cleared: new session 026d5981…`, then `08:35:15.752 [autoclear] effort: sent "/effort medium" (the screen showed max)`;
  - `08:54:40 cleared: new session 38f07bf2…` (`plan check: … step 16 open`), then `08:54:41.167 effort: sent "/effort medium" (the screen showed max)`.
- In both transcripts the `/effort medium` entries are hal2's (`hal2-cli-agents sent %10`: `source: autoclear`). `/clear` itself keeps the effort: the screen read `max` right after it.
- The cause is `~/.config/hal2/agents.toml` `[autoclear] effort = "medium"` (the user, 2026-10-06), applied by:
  - `apps/hal2-cli-agents/src/main.rs:438` `effort: args.effort.or(settings.effort)`;
  - the guard's `start_job` (`libs/hal2-agents/src/guard.rs:745-756`), which passes no `--effort`;
  - the sweep (`libs/hal2-agents/src/sweep.rs:357`, `effort: settings.effort`);
  - the job itself: `libs/hal2-agents/src/autoclear.rs:1427-1431` runs `clear()`, `save_defaults()`, `set_effort()`, `restore_defaults()` and `send_prompt()`, and `autoclear/effort.rs:61-79` types `/effort <level>` whenever the screen shows another level.
- Restarts lose a live level as well. `libs/hal2-agents/src/restart.rs:95-112` and `restart/replace.rs:86-95` (`effort_from_command`), and `restore.rs:57-58,70-76`, read `--model` and `--effort` only from the old process's argv. A live `/effort max` never appears there.
- `[autoclear] tokens = 300000` is resolved once, against settings.json's 200k `opus` (`settings.rs:274-285,325-334`, `context.rs:195-213,258-262`). That gives 100%, so it never applies, and on a 1M session the guard stops at 35% alone.

## The contract with the skills

- A plan's coordinator values are the plan.md front matter key `run: <model> <effort> <window>`, for example `run: claude-opus-5-5 max 1m`.
  - The model is an alias (`opus`, `sonnet`, `haiku`, `fable`) or a full id (`claude-opus-5-5`), never with `[1m]`.
  - The effort is one of `low|medium|high|xhigh|max`.
  - The window is `200k` or `1m`.
  - hal2's records spec already allows `run`: it is a free string, and no spec change is needed.
- hal2 finds the plan the way `libs/hal2-agents/src/plan_guard.rs:44-62` (`open_plan`) already does: `<worktree>/plans/CURRENT_PLAN` (one line, the slug), then `<worktree>/plans/<slug>/plan.md`. No `CURRENT_PLAN`, no plan.md, or no `run` means no plan values, and hal2 falls through to the next source.
- A legacy plan (no front matter) has a `Run: <model> <effort>` line below its title and no window (`libs/hal2-core/src/plan_steps.rs:106-118` `run_default` reads it). Its window is the session's own.
- An unreadable or invalid field counts as absent and is logged. A partial `run` gives what it has.
- **Only the skills write plan.md, never hal2.** The coordinator runs `plan.py run --sync` at every step boundary, and `/handoff` runs it before it writes. So when a clear starts, `run` holds the session's live values as of the last step at the latest.

## The changes

### 1. Clear-and-continue restores the effort and the model

Files:

- `apps/hal2-cli-agents/src/main.rs:438,479-480`; `lib.rs:656-658` (the `--effort` help);
- `libs/hal2-agents/src/autoclear.rs:1427-1431` (`execute`) and `:1957-1967` (`log_plan`);
- `autoclear/effort.rs:1-12,23-26,61-79` (`set_effort`); `scrape/effort.rs:1-13` (`claude_effort`);
- `guard.rs:745-756`; `sweep.rs:357`; `plan_guard.rs:44-62`;
- `libs/hal2-core/src/plan_steps.rs`;
- the switch: `restart.rs:115-136`, `apps/hal2-cli-agents/src/switch.rs:100-113`, `switching.rs:57`.

New behaviour:

- `plan_steps.rs` gets a pure `run_values(plan_text) -> Option<RunValues { model, effort, window }>`. It reads the `run` key, else the legacy `Run:` line. `plan_guard.rs` gets `run_values(cwd)` on the `open_plan` path, plus an `Env` hook so that tests can script it.
- `Request.effort` holds an explicit `--effort` only. `main.rs:438` stops folding in `settings.effort` and passes it as a new `Request.fallback_effort` instead. `sweep.rs:357` and the guard's `start_job` do the same.
- In `execute`, read `live` **before** `/clear`: `scrape::claude_effort(screen)`, else the process's `--effort`.
- The target effort is the first of:
  1. the explicit `--effort`;
  2. the plan's `run` effort;
  3. `live`;
  4. `[autoclear] effort` (the fallback only).

  `set_effort` types nothing when target equals live. So a session with no plan and a live `max` keeps `max`.
- Log `effort: target <x> from <explicit|plan|live|fallback>` and add `effort_source` to the `JobRecord`. On the busy path, never type the fallback over a live level.
- **Model.** When `run` names a model and the live model (transcript `message.model`, else the process's `--model`) differs, do not type `/clear`. Restart through the existing switch (`restart::switch`, Launch `{model, effort: target, prompt: the job's prompt, normally "/handoff c"}`) and never type `/model`. Compare models without `[1m]`, so an alias equals any id of its family (`opus` = `claude-opus-5-5`).

Tests:

- `plan_steps` parses a full `run`, the legacy `Run:` line, a missing key, a bad effort (None) and a two-word `run` (no window).
- Scripted pane:
  - `run` max, screen max, fallback medium: nothing is typed;
  - `run` high, screen max: `/effort high`;
  - no plan, screen max, fallback medium: nothing is typed;
  - explicit `--effort low` beats everything;
  - no `CURRENT_PLAN`: the old behaviour minus overriding a live level.
- **Incident replay** `incident_dev10_tests.rs`: pane %10 at 08:54. The plan `0003-…` has `run: claude-opus-5-5 max 1m`, the screen shows `max`, agents.toml says `medium`. Assert that no `/effort medium` is sent and the log says `target max from plan`. A variant without `run` asserts `target max from live`.
- Model mismatch: `run` names `sonnet`, the live model is `claude-opus-5-5`. Assert the switch path with `/handoff c` and no `/clear`.

### 2. Restarts take model and effort from the plan

Files: `libs/hal2-agents/src/restart.rs:95-112,115-136`; `restart/replace.rs:86-95`; `restore.rs:57-58,70-76`; `spawn.rs:112-158` (`Launch`, `push_flags`). They cover the switch, the remote-control restart, the terminal-host restore and the orphan restart.

New behaviour: a flag the caller leaves unset comes from the plan's `run` when the worktree has a current plan, else from the old process's argv. For example, `old = asked.or(run).or(argv)`.

Window to flags: `1m` passes the model as hal2 does today (an alias maps to `<alias>[1m]`). `200k` cannot come from the model id: a 5.x id without `[1m]` still gets 1M (skills research 0004, findings/claude-code.md; a `claude-opus-5-5` session held 225k tokens without compacting), so `200k` means starting the process with `CLAUDE_CODE_DISABLE_1M_CONTEXT=1`; log it, and treat `200k` as rare.

Tests: argv without `--effort` plus `run` max gives `--effort max`; an explicit flag beats `run`; with no plan, argv is used as today; the restore of a recorded `worktree run` in a plan slot takes `run`.

### 3. `hal2-cli-agents spawn --effort`

Files: `apps/hal2-cli-agents/src/lib.rs:42-43` (spawn takes `--model` only) into `spawn.rs` `Launch`/`push_flags`. Update the `clear-and-continue --effort` help (`lib.rs:656-658`): plan 0214's per-step switch is obsolete, because steps now run in subagents. Tests: parsing, and `--effort` reaches the claude command line.

### 4. The guard resolves `[autoclear] tokens` per session window (D17)

Files: `libs/hal2-agents/src/settings.rs:274-285` (`resolve`), `:325-334` (`AgentsSettings::load`); `guard.rs:598,710-715`; `sweep.rs:533-538`; `session_window.rs:8-15,49-71`.

New behaviour: keep `tokens` and `step_tokens` raw at load. A new `AutoclearSettings::threshold_for(window)` runs at check time against `session_window(...)`, the window of that session. The threshold is the lower of `percent` and `tokens` as a percent of that window, and the same for `step_*`. A `tokens` value above the window is ignored. `settings --json` shows the raw values.

Tests: `tokens = 300000` on a 1M session gives 35 (`min(35, 35.9)`, usable window); `tokens = 200000` on 1M gives 23 (35 today); a 200k session ignores `tokens = 300000`.

### 5. Optional: display only

`libs/hal2-core/src/plan_steps.rs:10-27` (`Columns`) reads the `Window` and `Size` columns. `libs/hal2-plans/src/document.rs:8-10,112,222-223` reads `run` with the other front matter keys (`Plan.run`), and `hal2-cli-plans show --json` serializes them. hal2 never acts on step values.

## The decisions behind them

- **D10:** "Before a clear the live session wins, after it the plan wins: the coordinator syncs `run` at every step boundary and `/handoff` syncs it before writing; `/handoff c` compares and, when model or effort differ, restarts once through `hal2-cli-agents switch`."
- **D11:** "hal2's clear-and-continue (also when its guard or sweep starts it) restores the effort from the plan's `run`, else the level the session runs at; `[autoclear] effort` becomes the last fallback. hal2 never writes plan.md: only the skills do."
- **D16:** "context.py takes the 5.x models' window as 1m (`[1m]`-less ids included, unless `CLAUDE_CODE_DISABLE_1M_CONTEXT=1`) and reports drift between the session and the plan's `run`."
- **D17:** "resolve `[autoclear] tokens` against each session's own window (the lower of tokens and percent stops), as hal2 research 0048 intended."
- The user (D1): "after the handoff and the clear, the effort level was changed to medium so I think we should also ensure that the handoff updates the current plans, model, effort, and context window size [...] I think it is good to persist that in the plan file."

## What the skills repository does in its own plan

- `plan.py new` writes `run: <model> <effort> <window>` from the session's live values. `plan.py run --sync` keeps it current at every step boundary and in `/handoff`, and `plan.py run --check` compares.
- `/handoff c` restores: if the session's model or effort differ from `run`, it restarts once with `hal2-cli-agents switch --model --effort --prompt "/handoff c" --detach --json`. `/handoff clear` calls `clear-and-continue --effort <run's effort>`.
- context.py treats the 5.x models as 1m and reports drift against `run`. The live effort comes from the transcript, `$CLAUDE_EFFORT`, the process's `--effort`, then settings.
- Every step runs in a subagent. The servant starters (farmer delegation, fix-loc, sanity-watch, shoot) pass explicit `--model` and `--effort`. Scans skip sessions whose `hal2-cli-agents list --json` `background_tasks` is not empty.
- No new subservant sessions. The skills' `plans/LEAD` guards stay until no slot holds one.

## Open points for the hal2 servant to raise with its farmer

- Should the user's 2026-10-06 `[autoclear] effort = "medium"` remain at all? D11 keeps it as the last fallback, for sessions with no plan and no readable level. Removing it would change only those sessions.
- Should hal2 write the live effort back into plan.md? D11 says no, only the skills write it. Raise it if a path has no skill to sync, such as a user's `/effort` between two steps.
- The busy path today logs "No /effort on this path". Should it now type the plan's level, or keep typing nothing?
- Model equality: is "same family after stripping `[1m]`" enough, or should a full id in `run` that differs from the live id (`claude-opus-4-6` against `claude-opus-5-5`) also force the switch? The draft says yes for differing full ids.
- hal2 slots 31-33 still hold `plans/LEAD` of hal2 plan 0149. Its lead should convert its open rows to subagent steps; then the stale slots can be pruned and hal2-git's LEAD guard can follow later.
- If hal2-nvim lives in hal2: its `templates/shot-template-single.md` item 7 should say "make it a plan and run it as its coordinator: every step in a subagent at its Model, Effort and Window".

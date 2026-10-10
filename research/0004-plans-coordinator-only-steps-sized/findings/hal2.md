# Findings: where hal2 loses the coordinator's effort (plan 0015, step 5)

Read-only, 2026-10-10, hal2 main checkout `~/a/hal2` (paths below are relative to `~/a/hal2/code/rust/`), hal2 state
`~/.local/state/hal2/agents/`, `~/.config/hal2/agents.toml`, running processes.

## Summary

- The clear-and-continue job types `/clear` into the **same** claude process (no restart). Then, when `[autoclear] effort` is set, it types `/effort <level>`. The user's `agents.toml` has `effort = "medium"`.
- Proof: pane %10 (`~/a/dev` main) logged `effort: sent "/effort medium" (the screen showed max)` after its own `/clear` at 08:35:15 and again at 08:54:41. hal2 overwrote the user's `max` on purpose, as configured.
- `/clear` keeps the effort: the screen read `max` right after the clear. Only hal2's typed `/effort` changed it.
- No hal2 code reads a plan's coordinator settings. hal2 reads plan.md only for open steps and for per-step `Model`/`Effort` columns plus `Run:` (shown as data, never acted on). Restarts take model and effort from the old process's argv, which never sees a live `/effort`.
- `[autoclear] tokens = 300000` is converted to a percent against settings.json's model (`opus` = 200k), giving >100%, so it never applies. The guard then measures 35% against each session's own window (dev: 1M, so about 292k tokens).

## Findings

1. **Clear-and-continue keeps the process.** `libs/hal2-agents/src/autoclear.rs:1-27` (phases: `/clear` typed and read back, then a `SessionStart` with source `clear` in the same pane, then the prompt). `autoclear.rs:1427-1431`: `clear()`, then `save_defaults()`, `set_effort(&new_session)`, `restore_defaults()`, `send_prompt()`. No `--model`/`--effort` process flags are involved, so the model and window stay those of the process.
2. **Where the effort comes from.** `apps/hal2-cli-agents/src/main.rs:438` `effort: args.effort.or(settings.effort)`: an explicit `--effort` wins, else `[autoclear] effort`. `main.rs:479-480` passes it on to the detached job. Callers:
   - the guard's `start_job`, `libs/hal2-agents/src/guard.rs:745-756`, passes no `--effort`, so `[autoclear] effort` applies;
   - the sweep, `libs/hal2-agents/src/sweep.rs:357`, uses `effort: settings.effort`;
   - the CLI flag `apps/hal2-cli-agents/src/lib.rs:656-658` is documented as "typed after the clear instead of agents.toml's `[autoclear] effort` (plan 0214 step 1: a plan step's own level)".
3. **What `[autoclear] effort` does.** `libs/hal2-agents/src/settings.rs:16,225-227,263`: "the level the clear job sets in the new session". The typing is in `libs/hal2-agents/src/autoclear/effort.rs:1-12,23-26,61-79`:
   - nothing is typed when the screen already shows the level;
   - otherwise `/effort <level>` is typed, overriding whatever the session ran at, and the "Change effort level?" dialog is answered "Yes".
   - The screen reading is `libs/hal2-agents/src/scrape/effort.rs:1-13`: the box corner `◐ max · /effort`, else the banner `with high effort`.
4. **settings.json side effect.** `libs/hal2-agents/src/claude_defaults.rs:1-8`: a typed `/effort` saves `modelSettings.<id>.effortLevel`, and hal2 puts back the saved default afterwards (`autoclear/defaults.rs:18-24`). Today's file: `opus`, `claude-opus-5-5: high`.
5. **Guard window.** `guard.rs:598` uses `threshold = settings.percent`. `guard.rs:710-715` measures `session_window::session_context` against the session's own window, `libs/hal2-agents/src/session_window.rs:8-15,49-71`, first found wins:
   - `CLAUDE_CONTEXT_WINDOW`;
   - the statusline's `<records>/<session>.window` (or 1M for a `[1m]` id);
   - inferred from `<session>.context`;
   - settings.json's model.

   The sweep does the same: `sweep.rs:533-538`.
6. **Tokens ceiling uses the wrong window.** `settings.rs:274-285` `resolve(window)` turns `tokens`/`step_tokens` into percents. `settings.rs:325-334` (`AgentsSettings::load`) resolves them once, against `context::claude_configured_window`, `libs/hal2-agents/src/context.rs:195-213,258-262`, which is settings.json's `model` (`opus`, so 200k), not the session's window. `tokens = 300000` on 200k gives `percent_of = 100`, so `percent` stays 35 (as `settings --json` shows: `percent 35`, `step_percent null`). On a 1M session the 300k ceiling is never applied as tokens.
7. **`hal2-cli-agents switch`.** `apps/hal2-cli-agents/src/switch.rs:1-4,10,100-113` and `switching.rs:57` stop by signal and start a fresh session in place with `--model`/`--effort` and the first prompt `/handoff c`. The logic is in `libs/hal2-agents/src/restart.rs:1-17,115-136`. Unset flags fall back to the old session's.
8. **Restart keeps only argv.** `restart.rs:95-112` and `libs/hal2-agents/src/restart/replace.rs:86-95` read `--model`/`--effort` from the old process's command line (`effort_from_command`). A live `/effort max` is invisible to them. `~/a/dev`'s process `65403 claude --remote-control dev-main --dangerously-skip-permissions --continue` has neither flag, so a restart comes back at settings.json's `high`. `libs/hal2-agents/src/restore.rs:57-58,70-76` (terminal host restore) does the same from the recorded `worktree run` args.
9. **`hal2-cli-git worktree run --model --effort`.** `apps/hal2-cli-git/src/lib.rs:26,64-65,258-260,358-359,534` parse the flags. `lib.rs:1033-1060` `agent_command` builds `claude --remote-control <repo>-<slot> --dangerously-skip-permissions [--model m] [--effort e]`, then either `-- <prompt>` or `--continue ... || claude`. These are per-process flags, saved nowhere. `libs/hal2-agents/src/spawn.rs:112-158` (`Launch`, `push_flags`) passes them on.
10. **`hal2-cli-agents spawn`.** `apps/hal2-cli-agents/src/lib.rs:42-43` takes `--model` only, **no `--effort`**.
11. **What hal2 reads of plan.md.**
    - `libs/hal2-agents/src/plan_guard.rs:44-62` `open_plan`: `plans/CURRENT_PLAN`, then `plans/<slug>/plan.md`, then whether steps are left. The job only logs it (`autoclear.rs:1957-1967` `log_plan`).
    - `libs/hal2-core/src/plan_steps.rs:8-11,106-118`: the step table's `Model`/`Effort` columns and `run_default` (`Run: <model> <effort>` below the title).
    - `libs/hal2-plans/src/document.rs:8-10,112,222-223`: front matter keys `created, grilled, finished, landing, autogenerated`, plus `Step.model/effort` (serialized by `hal2-cli-plans show --json`).
    - Nothing acts on step model/effort, there is no `run`/`coordinator` front matter key, and hal2-macos (`code/swift`, outside `.build`) has no effort or model code.

## Evidence

- `~/.config/hal2/agents.toml`: `[autoclear] effort = "medium"` (comment: the user, 2026-10-06, "also set the effort levels for all sessions to medium"), `tokens = 300000`. `hal2-cli-agents settings --json`: `percent 35, tokens 300000, step_tokens null, step_percent null, effort "medium"`.
- `~/.local/state/hal2/agents/autoclear/10.log` (pane %10 = `~/a/dev`, guard.log `cd /Users/mod/a/dev`):
  - `06:27:54` and `07:14:46`: `effort: the screen shows medium already, nothing typed`;
  - `08:35:14` `continuing: cleared: new session 026d5981…`, then `08:35:15.752 effort: sent "/effort medium" (the screen showed max)`, then `08:35:16 the screen shows medium`;
  - `08:54:40` `cleared: new session 38f07bf2…` (`plan check: plan 0003-tmux-ghostty-and-alfred-pane-switcher, step 16 open`), then `08:54:41.167 effort: sent "/effort medium" (the screen showed max)`.
- Transcripts `~/.claude/projects/-Users-mod-a-dev/026d5981….jsonl` and `38f07bf2….jsonl`: `<command-name>/effort</command-name><command-args>medium` at 06:35:15Z and 06:54:41Z (UTC = 08:35/08:54 local). `hal2-cli-agents sent %10`: both entries have `source: autoclear`. The user's own switch to `max` is in no transcript or sent log (it was set some other way; see Open questions).
- Guard marker `026d5981….guard`: `stage soft, percent 35.0, threshold 35`. Statusline windows: `026d5981….window = 1000000`, `38f07bf2….window = 1000000`. Transcript model `claude-opus-5-5`.
- `ps`: hal2-launched slots carry flags (`claude --remote-control hal2-43 … --model opus[1m] --effort max -- /handoff c`), while main checkouts do not (`dev-main … --continue`).

## Draft of the hal2 change

**Goal:** a clear (by the job, the guard or the sweep) or a restart (switch, `remote-control restart`, terminal restore) brings the coordinator back at the plan's model, effort and window.

**Source order.** Recommended: the plan's front matter, kept in sync with the live session by the handoff.

- **Effort:**
  1. explicit `--effort` on the request;
  2. the `coordinator` key in plan.md's front matter, for the plan that `plans/CURRENT_PLAN` (in the session's checkout) names;
  3. the live level on screen (`scrape::claude_effort`, read **before** `/clear`). For a same-process clear this means typing nothing;
  4. the old process's argv `--effort` (restarts only);
  5. `[autoclear] effort`, demoted to a fallback for sessions with no plan coordinator.

  The plan is the persisted truth because the handoff skill writes the live values into it before every hand-off: effort from `$CLAUDE_EFFORT` (claude-code.md finding 4), model and window from context.py `session_model`. A user's mid-run `/effort max` therefore reaches plan.md before the clear. Taking only the running process's value would survive a `/clear` (it does today without `[autoclear] effort`), but it is lost on any restart and invisible to a fresh slot.
- **Model:**
  1. explicit;
  2. coordinator;
  3. argv;
  4. none.

  If the coordinator model differs from the live one (transcript `message.model` plus the `.window` file), the job must **switch** (`restart::switch` with `--model`, `--effort`, `--prompt <kind.prompt>`) instead of `/clear`, never a typed `/model`.
- **Window (guard, sweep, `tokens` resolve):**
  1. `CLAUDE_CONTEXT_WINDOW`;
  2. the statusline `.window`;
  3. the coordinator window;
  4. `[1m]` in the session's model id (argv `--model`, like context.py `session_model`);
  5. inferred from `.context`;
  6. settings.json.

  Yes: the guard's window must come from the session's model. It already does for the percent (`session_window`), but not for `tokens`.

**Front matter key.** `coordinator: <model> <effort> <window>`, e.g. `coordinator: opus[1m] max 1m`. Each field may be `-`, and the window is `200k`/`1m` or a number. This is a front matter key, not a body line (unlike `Run:`).

**Files and functions:**
- `libs/hal2-core/src/plan_steps.rs`: new pure `pub fn coordinator(front_matter: &str) -> Option<Coordinator { model: Option<String>, effort: Option<String>, window: Option<u64> }>`, next to `run_default`.
- `libs/hal2-plans/src/document.rs`: read `coordinator` with the other front matter keys, `Plan.coordinator`, in `show --json`.
- `libs/hal2-agents/src/plan_guard.rs`: `pub async fn coordinator(cwd) -> Option<Coordinator>`, using the same CURRENT_PLAN to plan.md path as `open_plan`. Add an `Env::coordinator(cwd)` for the job, the guard and the sweep (scriptable in tests).
- `libs/hal2-agents/src/autoclear.rs`:
  - `execute` (`:1427`): before `clear()`, read `live = scrape::claude_effort(screen)` and `target = request.effort.or(coordinator.effort).or(live).or(settings fallback)`;
  - `effort.rs` `set_effort` takes `target` (and types nothing when `target == live`);
  - log `effort: target <x> from <source>`;
  - add `effort_source` to the `JobRecord`.
  - `Request.effort` stays the explicit override only. `main.rs:438` stops folding in `settings.effort`; pass `settings.effort` as `Request.fallback_effort` instead. Do the same at `sweep.rs:357`.
- Model mismatch: in `execute`, when `coordinator.model` is set and differs from the live model, call `restart::switch` (Launch{model, effort, prompt}) instead of `clear()`.
- `libs/hal2-agents/src/restart/replace.rs:86-95`: `old = asked.or(coordinator).or(argv)`, so a restart of a plan session comes back at the plan's values.
- `libs/hal2-agents/src/settings.rs:325-334` and `guard.rs:598` / `sweep.rs`: resolve `tokens`/`step_tokens` per session, against `session_window(...)`, at check time (a new `AutoclearSettings::threshold_for(window)`) instead of once at load.
- `apps/hal2-cli-agents/src/lib.rs:42`: add `spawn --effort`. Update the `clear-and-continue --effort` help text, which mentions plan 0214's per-step switch, now obsolete because steps run in subagents.

**Tests:**
- `plan_steps.rs`: parses a full key, `-` fields, `1m`/`200k`/number windows, bad effort gives `None`, a missing key gives `None`.
- `autoclear/effort_tests.rs` (scripted pane):
  - coordinator `max`, screen `max`, `[autoclear] medium`: nothing typed;
  - coordinator `high`, screen `max`: `/effort high`;
  - no coordinator, screen `max`, fallback `medium`: nothing typed (live wins over the fallback);
  - explicit `--effort low` wins over everything.
- `incident_dev10_tests.rs`: replays 10.log 08:54 (plan 0003, coordinator `max`, screen `max`, `agents.toml` medium) and asserts no `/effort medium` is sent.
- `restart_tests.rs`: argv without `--effort` plus coordinator `max` gives `--effort max`.
- `settings`/`guard` tests:
  - `tokens = 300000` with a 1M session gives a threshold of `min(35, 35.9) = 35`;
  - `tokens = 200000` with a 1M session gives 23 (today it is 35);
  - a 200k session ignores tokens.
- `switch_tests`: a model mismatch takes the switch path with `/handoff c`.

## Open questions

- Q1: Should `[autoclear] effort = "medium"` (the user's 2026-10-06 rule "set the effort levels for all sessions to medium") still apply to sessions without a plan coordinator, or only to sessions hal2 starts? The draft keeps it as the last fallback and lets a live level beat it.
- Q2: Should hal2 itself write the live effort back into plan.md when it differs (it never edits tracked files today), or does only the handoff skill write it? The draft has only the handoff skill write it.
- Q3: How the user set `max` in the dev session is not in any transcript or sent log (a `/effort max` is session-only per claude-code.md; possibly the `/model` slider or Remote Control). Whether the handoff skill's `$CLAUDE_EFFORT` sees a slider change is not verified.
- Q4: Does `/clear` keep the **model**? The code never changes it and the `.window` stayed 1M across clears, but there is no direct test.
- Q5: The `tokens` ceiling resolved per session changes when 1M sessions stop (e.g. `tokens = 300000` vs 35% of 1M usable ≈ 292k). Should `tokens` win over `percent` there, as research 0048 intended?

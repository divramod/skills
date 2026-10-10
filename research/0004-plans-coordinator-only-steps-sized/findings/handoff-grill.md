# Findings: handoff and grill (plan 0015 step 2)

## Summary

- The effort is lost because hal2 types it. agents.toml `[autoclear] effort = "medium"` makes every clear job type `/effort medium` after `/clear`, whatever the plan's coordinator ran at. `clear-and-continue --effort <e>` already overrides that setting (hal2 `main.rs:438`, `args.effort.or(settings.effort)`), and the job restores the saved defaults around the typed `/effort`.
- The session's values can be read without asking. Every main-chain assistant entry of the transcript carries `"effort"` and `message.model`, and `/effort` writes `Set effort level to <e> (...)` like `/model` writes `Set model to ...`. There is also `$CLAUDE_EFFORT`, the claude process's `--effort` (`$CLAUDE_PID`) and settings.json `modelSettings.<id>.effortLevel`.
- The handoff persists nothing about the session today. It should sync `run: <model> <effort> <window>` into plan.md through a new `plan.py run` command, and the coordinator's loop should do the same at every step boundary. `/handoff c` restores the other way, from plan.md to the session.
- The autogrill (grill `## Auto`) does not mention Model, Effort or Window. Its rubric lives in plan SKILL.md:211-214 and has no window and no sizing.
- Sizing problem: a general-purpose subagent here starts at about 83k tokens, measured in this plan's own subagents. 35% of 200k is 70k, so no such step fits a 200k window. The rubric has to budget against 1m, or count only the step's own work.

## Findings

1. **What the handoff writes today.**
   - `where.py --stamp` (where.py:57-71) sets handoff.md's `updated`, `branch`, `at` and `status`.
   - Step 1 of Write appends `D<n>` entries to decisions.md (SKILL.md:102-138). Step 2 appends `Q<n>` entries to questions.md (`questions.py`, SKILL.md:140-170).
   - `commit-handoff.sh` commits exactly the named docs in a temporary index (commit-handoff.sh:74-95).
   - Nothing writes the session's model, effort or window anywhere. plan.md's front matter key `run` exists, but plan.py reads it only as the default for empty step cells (`run_default`, plan.py:249-253, used at :258 and :276-277). Plan 0015 already uses `run: claude-opus-5-5 max` to mean "the coordinator's" (plans/0015.../plan.md:9), without a window.
   - Change: Write gets a step "3b. Persist the coordinator's values": `plan.py run --sync`, before `where.py --stamp`, with plan.md added to the commit. Why: plan.md is the one committed record the next session reads, on another machine too.
2. **Where the session's values can be read, deterministically.**
   - Model: context.py `session_model` (context.py:108-121) takes the transcript's `/model` line, then the claude process's `--model`, then `$ANTHROPIC_MODEL`, then settings.json `model` (here `"opus"`).
   - Effort, checked on this machine:
     - (a) Every main-chain assistant entry carries `"effort":"max|high|..."` (this session: `max`) and `"perTurnEffort"` (a one-turn override; ignore it).
     - (b) A `/effort` change is recorded as a user entry `<local-command-stdout>Set effort level to <e> (saved as your default for new sessions | this session only)`. Counts across all transcripts: 40 medium, 6 high, 7 max ("this session only"). A cancelled change reads `Kept effort level as <e>`.
     - (c) The claude process's `--effort` is set by hal2 starts (`ps`: `--model opus[1m] --effort max`). `$CLAUDE_PID` names that process directly, with no walk up the `ps` tree.
     - (d) `$CLAUDE_EFFORT` is exported into tool shells. Inside a subagent it is the subagent's effort (`high` here, while the coordinator is at `max`).
     - (e) settings.json `modelSettings.<model-id>.effortLevel` (opus: high, sonnet: medium) is the saved default.
   - Window: `message.model` never carries `[1m]` (55k entries checked), so the window still comes from the model name (`[1m]`, "1M context") or from use above 200k (context.py:124-129, :202-203).
   - Change: one function that returns all three values and the source of each (Proposed 1).
3. **The coordinator's model and window survive a clear. Its effort does not.**
   - `/clear` keeps the process, so the process's `--model` and an in-session `/model` both stay.
   - The effort is reset by hal2's clear job: autoclear.rs:1428-1430 runs `save_defaults`, then `set_effort` (types `/effort <[autoclear] effort>`), then `restore_defaults`. The user's agents.toml line 1 says it was set on purpose for all sessions (2026-10-06).
   - `clear-and-continue --effort <e>` exists today and overrides that setting. `switch --model --effort --prompt "/handoff c"` restarts the process with process-only flags and saves nothing.
   - Note: hal2 maps `switch --model opus` to `opus[1m]`, so a 200k coordinator needs the full id (`claude-opus-5-5`).
4. **Restore on `/handoff c`.** Continue step 1 reads plan.md (SKILL.md:46-50) but never compares the session with anything.
   - Change: a step 0 runs `plan.py run --check`. When the values match, go on. When they differ, `switch --model <m'> --effort <e> --prompt "/handoff c" --detach --json` and end the turn. A restart right after a clear costs nothing, since the context is empty.
   - Effort only differs: still `switch`. The agent cannot type `/effort` itself, and a typed `/effort high` would save the user's default.
   - `switch` refused (exit 3, no hal2): go on and note it under the handoff's Watch out.
   - Loop guard: when `switch` already ran for this handoff (`at`) and the values still differ, do not switch again. Write `plan.py run --sync`, since the session wins, and say so.
5. **Mid-plan `/model` or `/effort` must reach plan.md.**
   - Today nothing reads either. The plan SKILL forbids the agent to type `/model` (plan SKILL.md:216-218); the user may still type it.
   - Change: sync at both points. At every step boundary, Finish a step point 5: `context.py` already reads the transcript there, so `plan.py run --sync` costs one call and goes into the step commit. At the handoff, Write step 3b.
   - Direction rule: session to plan only in a session that has finished at least one step or a handoff write. `/handoff c` goes plan to session (point 4). Otherwise hal2's typed `/effort medium` would overwrite `max` in plan.md.
6. **The grill's autogrill.**
   - grill SKILL.md:67-82 decides branches and records them; it has no word on Model, Effort or Window. The picking rubric is plan SKILL.md:211-214 (Opus high for design, xhigh for a pivotal decision, Sonnet medium/high for specified work, Haiku for narrow mechanical work).
   - Measured base cost of a subagent in this repo (this plan's subagents' first API call): general-purpose about 83k tokens, claude-code-guide about 35k. Steps 1-5 already passed 150-190k, so they ran past 35% of any 200k window.
   - The subagent's `meta.json` records the model and effort it really ran with (`subagents/agent-*.meta.json`: `"model":"opus","effort":"high"`). That is a deterministic check that a step ran at its row's values.
7. **Tests.** All handoff tests are `unittest` (`test_*.py`, run by `python3 -m unittest discover -s scripts`). They build temporary git repos with `subprocess` and `tempfile`. context.py's tests are `skills/plan/scripts/test_context.py`.

## Proposed changes

1. **`skills/plan/scripts/context.py`: `session_values(transcript, settings) -> dict`**, with CLI `context.py --session-values` that prints `{model, effort, window, sources:{model, effort, window}}`. Sources in order:
   - Effort: the later in transcript order of the last `Set effort level to (\w+)` line and the last main-chain assistant `effort`; then `$CLAUDE_EFFORT`, unless `CLAUDE_CODE_CHILD_SESSION` or a subagent marks it as not the coordinator's; then the claude process's `--effort` (via `$CLAUDE_PID`, else `process_model`'s walk extended to `--effort`); then `modelSettings.<id>.effortLevel`; then `effortLevel`; else `"default"`.
   - Model: `session_model` as now. Window: `configured_window`, raised to 1m when use is above 200k.
   - Reuse `last_usage` (extend it to return the effort too). Keep it in context.py rather than a new session.py: one transcript reader.
2. **`skills/plan/scripts/plan.py run`**:
   - `run --model <m> --effort <e> --window 200k|1m` sets front matter `run: <m> <e> <window>`; a legacy plan gets the `Run:` line.
   - `run --sync` reads `context.session_values()` and writes `run` when it differs, printing `{changed, before, after}`.
   - `run --check` exits 1 with `{plan, session, switch: [flags]}` when they differ. `switch` gives the flags: `--model <id>` for 200k, `--model <alias>[1m]` for 1m.
   - `run_default` stops filling empty step cells: every step row carries its own values, per (b). The plan skill's step 1 owns that.
3. **`skills/handoff/SKILL.md` Write**: a new "### 3b. Persist the coordinator's values". Text: "`python3 <plan-skill-dir>/scripts/plan.py run --sync` (a record plan run by its coordinator; not in a subservant's slot); plan.md goes into step 5's commit." Step 5's example list gains plan.md.
4. **`skills/handoff/SKILL.md` Continue**: a new step 0 as in finding 4, before step 1. The `/handoff clear` section and the plan's Finish point 3 pass the effort:
   `hal2-cli-agents clear-and-continue --effort <run's effort> --detach --json`.
5. **`skills/plan/templates/handoff.md`**: no change. The values live in plan.md, and the handoff names no session state.
6. **`skills/plan/SKILL.md` "Finish a step" point 5**: before `context.py`, run `plan.py run --sync` and amend the step commit with plan.md.
   "Model and effort per step" becomes "Model, effort and window": the per-step `switch` is gone, because steps run in subagents with the Agent tool's `model` and `effort`. `switch` remains only for restoring the coordinator (finding 4) and for `/plan start`.
7. **`skills/grill/SKILL.md` `## Auto`**: a new point 3b, "Size every step", and plan SKILL.md:211-214 links to it. The rubric:
   > Every step row has Model, Effort and Window. Model and Effort: Opus high for design, new engines and big rewrites; xhigh for a decision the plan turns on; Sonnet medium/high for well-specified work checked by a test; Haiku for narrow mechanical work. Window: 200k unless the step's estimate needs 1m. Estimate = the subagent's base (measure it: the first API call of a subagent of this agent type in this repo, about 83k for general-purpose here) + the files it reads (bytes/4) + the diffs it writes ×2 + test and build output + 10k for turns. A step must stay under 35% of its window counted above the base (the base is fixed, the step's own work is what grows); one that does not is split along its files or its checks into steps that do, or gets Window 1m when it cannot be split (one big file). Record each step's estimate in one line in the step's `steps/<n>.md` `## Approach` (`~<k> tokens: <what>`).
   - Whether 35% includes the base is open (Q1). The rubric above is the recommended reading.
8. **hal2** (to hal2-changes.md via step 7): the guard-started clear job (`already-running`) should take the effort from the current plan's `run` key when there is one, and only otherwise from `[autoclear] effort`.

## Tests to add

- `skills/plan/scripts/test_context.py`:
  - `session_values` from a fixture transcript with assistant `effort` entries and a later `Set effort level to max (this session only)` line: max, source "transcript /effort".
  - With only assistant entries: their last effort.
  - With an empty transcript: `CLAUDE_EFFORT`, then `modelSettings`.
  - `[1m]` model: window 1m.
- `skills/plan/scripts/test_plan.py`:
  - `run --model --effort --window` writes the front matter (record) and the `Run:` line (legacy).
  - `run --sync` changes nothing when equal and writes when different; it is refused in a subservant's slot (plans/LEAD).
  - `run --check` prints the switch flags, including the full id for 200k and `[1m]` for 1m.
- `skills/handoff/scripts/test_record.py`: a record plan whose `run` differs from a faked session (env plus fixture transcript via `--transcript`): `plan.py run --check` exits 1; after `--sync` and `commit-handoff.sh` with plan.md, the commit contains plan.md's new `run`.
- A unittest of the direction rule: the documented check that `/handoff c` never runs `--sync` before step 0, as a test that greps SKILL.md for the order, as other skills do.

## Open questions

- Q1: does "35% of the window" include the subagent's fixed base (about 83k here, 42% of 200k)? If it does, every general-purpose step needs Window 1m. Recommended: count only above the base, as in the rubric.
- Q2: can the Agent tool give a subagent a 1m window at all? Its `model` is only `opus|sonnet|haiku|fable`. Step 6 (Claude Code facts) answers it. Until then, Window 1m means "the subagent inherits a 1m parent".
- Q3: should the user's agents.toml `[autoclear] effort = "medium"` stay as the fallback for sessions without a plan? It was the user's explicit wish, 2026-10-06.

## Migration

- Running record plans without `run` or with a two-word `run`: the first `plan.py run --sync` at a step boundary or handoff writes `run: <model> <effort> <window>` from the session. Nothing has to be edited by hand.
- Legacy plans get the `Run:` line the same way. No `--check` restore happens without a value: a missing `run` means "take the session's".
- Plans whose step rows lack Model/Effort/Window: plan.py check reports them, and the next autogrill round, or the coordinator before the step, fills them by the rubric.
- Already-running sessions keep the clear job's typed medium until the skill passes `--effort` (Proposed 4) or hal2 reads `run` (Proposed 8). After that, the first `/handoff c` restores the persisted effort through `switch`.

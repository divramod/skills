# Findings: the plan skill (plan 0015 step 1)

## Summary

- Today a step's Model and Effort pick the *session* (`hal2-cli-agents switch` restarts it). Steps run in that session, or in subservant sessions in slots 30-99. Nothing sizes a step, and there is no Window anywhere in the table.
- Adding `Window` (and a `Size` estimate) is a small change to `read_steps`. The check goes into `plan.py check` as a plan.py rule, because hal2's checker never looks at step columns. hal2's spec rejects unknown front matter keys (verified). So the coordinator's values should go into the existing free-string `run` key: `run: opus max 1m`.
- About 60% of parallel.py, its tests and two SKILL.md sections (about 135 lines) are subservant machinery and can go. Needs/Touches/`ready` stay for parallel subagents.
- Measured: a general-purpose subagent here *starts* at about 83.5k tokens (all MCP tools plus the skill list). That alone is over 35% of 200k. The rubric must count work above the baseline, or steps must run in a lean agent type (about 35k).
- context.py takes the window from the process's `--model`. The live 0015 coordinator (`--model claude-opus-5-5`, no `[1m]`) shows 199k used and is not compacted, so the 200k guess is wrong there. The plan's `run` window should feed context.py, and context.py should report drift between the plan's values and the session's.

## Findings

1. **Table parsing** (`skills/plan/scripts/plan.py:239-284`). `steps_table` finds the first table whose header has `#`, `Step` and `Status` and returns every lower-cased column position. `read_steps` reads `#`, `step`, `done when`, `status`, `model` and `effort`. An empty model or effort cell falls back to `run_default` (`plan.py:249-253`, the first two words of `run`/`Run:`). Parallel tables add `needs`, `touches` and `who` (`parallel.py:93-98`). Adding `window` is one more `cols.get` line. `size` works the same way. `set_cells` already writes any named column. hal2 has its own copy of this parser (`hal2/code/rust/libs/hal2-core/src/plan_steps.rs:10-27`, `Columns` with model and effort only, `run_default` reading `Run:` lines only). hal2-plans uses it at `document.rs:112`, so hal2 needs `window` too, for display only.
2. **The check today** (`plan.py:687-732`, `checker.py:41-55`). `run_check` checks plan-number collisions with `plan_number.py`, then runs `hal2-cli-records check --json --repo|--folder` and keeps the problems under `plans/`. Legacy plans pass because hal2 skips files without `type`. hal2's Plan spec (`hal2/code/rust/libs/hal2-records/specs/plan.toml`) checks keys, sections and budgets. Its code rules (`plan_rules.rs:64-91`) check only step numbers and status against the table, never Model, Effort or Window. So without new code, a plan with no Model, Effort or Window passes today.
3. **Unknown front matter key** (verified on a scratch copy with `--folder`). Adding `coordinator: claude-opus-5-5 max 1m` gives `unknown key coordinator (spec:unknown-key)`, because `hal2-cli-records schema plan` has `"additionalProperties": false`. `run: claude-opus-5-5 max 1m` passes: `run` is a non-empty free string (plan.toml: "the session's model and effort for every step that names none"). Plan 0015 already uses `run` as "the coordinator's".
4. **Model and effort today pick the session** (`SKILL.md:207-233`). A different model or effort means `/handoff` plus `hal2-cli-agents switch --model --effort --prompt "/handoff c"`. `/plan start` (`SKILL.md:148`, `231-233`) always switches into a fresh session. Run the plan (`SKILL.md:285-294`) has the session implement each step itself ("Implement it until its done-when check passes"). This is the core of what must change.
5. **Subservant machinery** (`SKILL.md:53-56`, `153-158`, `301-433`; `parallel.py:13`, `21-26`, `173-322`; `plan.py:57-74`, `735-829`; `templates/step-brief.md`, `templates/report.md`). This covers `assign … slot NN`, the `plans/LEAD` marker (`read_marker`, `write_marker`, `subservant_marker`, `refuse_subservant`), the farmer-ledger lookups, `brief_prompt`, `arrived`, `reports` and `watch`. All of it exists only for sessions in slots 30-99. The DAG part (`parse_needs`, `parse_touches`, `capacity`, `problems`, `schedule`, `kind`, `holds`) is agent-agnostic.
6. **Context check** (`context.py:108-129`, `168-208`). The window is `--window`, else `$CLAUDE_CONTEXT_WINDOW`, else the model from the transcript's `/model`, else the process's `--model`, else `$ANTHROPIC_MODEL`, else settings.json. It is 1M only when `[1m]` or "1M context" appears in the name. The threshold is hal2's `step_percent`, else `percent`, else 35. Live values are `percent 35, tokens 300000, step_percent null, effort medium`. context.py never reads the plan and knows nothing about effort.
7. **The live mismatch.** The `ps` process list shows `claude --model opus[1m] --effort max` in hal2-43 (plan 0228, whose plan says `run: opus max`, no window) and `--model opus[1m] --effort high` in hal2-02 (plan 0149, whose plan says `Run: opus medium`). The plan's `run` value is not what the session runs at, and nothing compares the two. That is the user's "effort was changed to medium" bug, seen from the plan side.
8. **Subagent baseline (measured)** from this session's `subagents/*.jsonl` first calls. general-purpose, opus or sonnet: 83.4-84.0k tokens. claude-code-guide (restricted tools): 35.4k. The Agent tool's `model` is an enum of aliases (`sonnet|opus|haiku|fable`, no full id, no `[1m]`), and `effort` is `low…max`. Step 6 must confirm what window a subagent gets.
9. **Templates.** `templates/plan.md:9` has `run: sonnet medium`, `:29-30` says "Model and Effort are the session's … the run switches the session", and `:32-35` has the table `| # | Step | Done when | Model | Effort | Status |` with empty model and effort cells in row 1. `templates/step.md` has no Size or approach budget. `templates/handoff.md` has no coordinator values.
10. **Tests** (89 pass today). Affected: `test_plan.py:91` (run default fills empty cells) and `:104` (new writes run and columns); `test_parallel.py:199-348`, `361-419` (assign slot, markers, farmer ledger, subservant refusal, brief prompt, reports and watch); `test_folder.py:64-83` (new plans must stay valid with the new columns); `test_context.py` (no plan or effort input yet).

## Proposed changes

**Valid values** (new `plan.py` constants):
- `MODELS = r"^(haiku|sonnet|opus|fable)$|^claude-(haiku|sonnet|opus|fable)(-[0-9a-z]+)+$"`, with no `[1m]` (that belongs in Window). The dispatch maps a full id to its family alias for the Agent tool.
- `EFFORTS = low|medium|high|xhigh|max` and `WINDOWS = {"200k": 200_000, "1m": 1_000_000}`.
- `Size`: `<n>k`, the estimated tokens of the step's work above the subagent's baseline. It must be at most `STEP_SHARE = 0.35` of the window: 70k for 200k, 350k for 1m.

**plan.py**
- `read_steps`: add `"window": cell("window") or run_window` and `"size": cell("size")`.
- `run_default` returns `(model, effort, window)`. Legacy plans keep the two-word `Run:` fallback for empty cells. Record plans do not: every row names its own values.
- New `steps_problems(text, slug)` for record plans only. Every row needs a valid Model, Effort and Window, and every open row a Size that is at most 35% of its window. `run` needs all three words, valid. Each problem reads `plans/<slug>/plan.md: step 3: Window '' is none of 200k, 1m (plan-steps-sized)`.
- `run_check` and `check_records` add these lines per plan folder, named or all, and exit 1 when there are any. `describe()['problems']` adds them, so `plan.py current` shows them too.
- New `plan.py run <model> <effort> <window>` sets the coordinator's values, plus `--from-session`, which takes them from context.py's detection.
- New `plan.py prompt <n>` prints the Agent call's JSON: `description` "Plan NNNN row n: <title>", `model` (alias), `effort`, and `prompt` (read `steps/<n>.md`, do only it, never edit plan.md, never commit, never land, return ≤15 lines: files changed, checks run with results, open points). This replaces `brief_prompt`.
- New `plan.py migrate [--window 200k]` for running plans, described under Migration.
- Delete `refuse_subservant`, `SUBSERVANT_REFUSES`, `report`, `reports` and `watch`. `assign` keeps `lead|subagent|user`. `slot NN` stays readable in done rows but can no longer be assigned.

**parallel.py**
- Keep `is_parallel`, `parse_needs`, `resource`, `parse_touches`, `kind`, `capacity`, `enrich`, `problems`, `holds` and `schedule`.
- Delete `LEAD`, `SUBSERVANT_SLOTS`, `slot_of`, `read_marker`, `worktree_of`, `subservant_marker`, `write_marker`, `slot_worktree`, `main_checkout`, `farmer_ledgers`, `farmer_servant`, `slot_taken`, `brief_prompt` and `arrived`.
- `WHO = lead|subagent|user`.
- Tests: delete `test_parallel.py` 199-348 and 361-419 except the `ready` and `who` checks. Add tests for `prompt`, `steps_problems` (missing, implausible and oversize values; legacy exempt; `run` without window) and `migrate`.

**Templates**
- `plan.md`: `run: opus medium 200k`. The note at lines 29-30 becomes: "`Model`, `Effort`, `Window` are the subagent's for the step, `Size` its estimated work, at most 35% of Window; `run` is the coordinator's own model, effort and window, the session that only dispatches."
- The table becomes `| # | Step | Done when | Model | Effort | Window | Size | Status |`, with row 1 `| | | 200k | | next` left for the autogrill to fill.
- `step.md`: add `Size: <n>k of <window> (<rubric line>)` under the Task.
- Delete `step-brief.md` and `report.md`. The step file is the subagent's brief, and its report goes into `## Notes`.
- `handoff.md`: a line `Coordinator: run <model> <effort> <window>` (handoff step 2).

**SKILL.md sections**
- *Front matter description*: "…runs it as its coordinator: every step in a subagent at the step's Model, Effort and Window, sized under 35% of that window; the coordinator's own model, effort and window persist in `run`…". Drop "subservant sessions in worktree slots 30-99", `assign`/`brief`/`report`/`reports`/`watch` and "a slot with plans/LEAD".
- *Good steps* (line 58): "fit one subagent: Size at most 35% of its Window (rubric below)".
- *Model and effort per step* becomes *Model, effort and window per step*. These are the subagent's. The coordinator never switches its own session for a step: it passes `model` and `effort` to the Agent tool. `run` names the coordinator, and only `/plan start` and the clear-and-continue restart the session, at `run`'s values. Escalation after two failed done-whens: a new subagent one effort level up, else the next bigger model, recorded in the step's Notes.
- *Run the plan* point 2: the coordinator never does a step itself. For each step it writes `steps/<n>.md`, runs `plan.py prompt <n>`, starts one Agent with it, then follows the loop below. Independent ready steps of a parallel plan go out as several Agent calls in one message, with Touches disjoint and builds serialized.
- *Run a parallel plan*: shrinks to about 15 lines. Needs/Touches/Who (`lead|subagent|user`), `ready --json`, parallel subagents, worktree isolation only with `baseRef: head`, shared files edited only by the coordinator, milestones unchanged.
- *Work as a subservant*: delete it, along with lines 53-56 and table rows 155-158.
- *`/plan start`* row: "the user's go: hand off, restart this session at the plan's `run` (model, effort, window) through `hal2-cli-agents switch`, which coordinates the plan to its landing without a question."
- *Finish a step*: the context check measures the coordinator only. Subagent context never counts. A coordinator turn costs about 5-15k (prompt, report, done-when output, diff stat), so one window covers many steps. The handoff records `run` and compares it against the session's values.

**context.py**
- Window precedence becomes `--window`, `$CLAUDE_CONTEXT_WINDOW`, transcript `/model`, process `--model` with `[1m]`, **then the current plan's `run` window**, then `$ANTHROPIC_MODEL` and settings.json. A `[1m]`-less `--model` no longer forces 200k when the plan says 1m (finding 7).
- Add `effort`, `effort_source` (process `--effort`, else settings `effortLevel`) and `drift` (a list such as `"effort medium, plan run says max"`). The coordinator fixes drift with `hal2-cli-agents switch` at its next step boundary.
- The 35% *step size* is plan.py's `STEP_SHARE`, independent of hal2's autoclear `percent`/`step_percent`, which stays the coordinator's clear threshold. Both happen to be 35 today. The step budget uses the raw window (70k/350k), because a subagent never reaches the 16.5% auto-compact buffer at 35%.

**Step-size rubric (for the autogrill; tokens of work above the baseline)**
- Read: about 12 tokens per line of code or markdown (a 300-line file ≈ 4k). Grep or ls output: 0.5-2k per call.
- Edit: about 1.5× the changed lines' tokens (old and new text) plus 0.5k per call. A new file is its size plus 0.5k.
- A test or build run: 1-3k when quiet, 5-15k when failing or verbose. Count 2 runs per check and add 1 fix round (about 5k).
- Fixed per step: 3-5k for the prompt and the final report.

| Kind of step | Typical work | ≤70k (200k) | ≤350k (1m) |
|---|---|---|---|
| Doc or prose edit, 1-3 files | 5-15k | yes | yes |
| Script change and its tests, 2-4 files ≤300 lines | 25-50k | yes | yes |
| Research or analysis reading 8-15 files (≈ this step) | 60-100k | split, or 1m | yes |
| Rust crate change with cargo build and test cycles | 60-120k | 1m | yes |
| Cross-crate refactor, 10+ files, or a big rewrite | 150-300k | no | split at 350k |

**The coordinator's loop**, one step at a time:
1. `plan.py current`, or `ready --json` for a parallel plan.
2. `plan.py status <n> next`; fill `steps/<n>.md` in 10-30 lines.
3. `plan.py prompt <n>`, then call Agent with that JSON (background for parallel steps).
4. Read the subagent's report only.
5. Run the done-when yourself and `git diff --stat`; use a review subagent for a large diff.
6. On failure: SendMessage the failure to the same subagent once, then escalate. If it still fails, notify and stop.
7. `plan.py status <n> done` and `status <n+1> next`, put the report's essentials in `## Notes`, commit `(plan NNNN step n)`.
8. `context.py`: when `stop`, hand off (with `run`) and clear-and-continue; when `drift`, switch first.

## Open questions

- What window does a subagent get? Can it be 1m, and does it inherit `[1m]` from the parent? The Agent tool takes no window (step 6). If a subagent is always 200k, `Window 1m` is not dispatchable, and the window cap is 200k.
- How to cut the 83.5k baseline. Options: a lean agent type in `.claude/agents/plan-step.md` (Read, Bash, Edit, Write, Grep; no MCP), or measuring Size above the baseline only. The code cannot settle this.
- Is Size a table column (checkable, one more cell) or a line in `steps/<n>.md` (written only when the step is next, so unchecked earlier)? Recommended: the column.
- Plausibility beyond set membership: haiku with `1m` or `xhigh/max`, `1m` with sonnet. Refuse only what step 6 confirms is impossible.
- Why does the 0015 coordinator (`--model claude-opus-5-5`, no `[1m]`) sit at 199k without compacting? Either Opus 5.5's default window is above 200k, or the usage sum overcounts (step 6 and step 5).

## Migration

- **Order.** Land plan.py's reading of Window/Size and `migrate` first, with `steps_problems` reported as warnings. Turn them into failures once the running plans have migrated. Then hal2 adds `window` to `plan_steps.rs` (display) and restores `run` on clear-and-continue (step 5). No hal2 spec change is needed, because `run` stays a free string.
- **`plan.py migrate`** (deterministic):
  - Insert `Window` after `Effort` and `Size` before `Status`, if missing.
  - Fill an empty Model or Effort from the old `run` default.
  - Fill Window with `--window` (default 200k).
  - Rewrite `run` to the session's values (`context.py`: model, effort, window).
  - Size stays empty. The coordinator estimates the open rows at its next `/handoff c`, in one short autogrill sizing pass.
- **0228 (hal2 slot 43)**: a record plan, sequential, Model and Effort in every row, `run: opus max`, the session at `opus[1m] max`. `migrate` gives `run: opus max 1m` and `Window 200k` per row. From its next step it dispatches subagents. Nothing else is in flight.
- **0149 (hal2 slot 02)**: legacy (no front matter, `Run: opus medium`), a 2273-line parallel table with Model/Effort, 46 open rows. Running now: 352 and 213, both subagents. Slots 31, 32 and 33 still hold `plans/LEAD` for steps 370, 164 and 160, which are all done.
  - It keeps passing the check as a legacy plan.
  - Its lead switches to the new loop at once. No subservant is running, so nothing is lost.
  - Delete the three stale `plans/LEAD` markers (or let the farmer prune the slots).
  - Optionally run `migrate --legacy` to add Window to its open rows.
  - hal2-git's LEAD guard and create.py `--lead` can be removed once no `plans/LEAD` exists in any slot (step 3 and step 5).
- **Other record plans** that predate this change fail the check until `migrate` runs. `/handoff` and `/mtm` run `plan.py check`, so they print `run plan.py migrate` as the fix. Legacy plans are never touched.

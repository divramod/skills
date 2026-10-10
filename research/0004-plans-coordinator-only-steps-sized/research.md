---
type: Research
schema: 1
id: 4
title: Plans coordinator only steps sized
description: What must change in every skill of this repository, and in hal2's autoclear, so that a plan's session only coordinates (every step in a subagent), every step carries Model, Effort and Window sized…  # one sentence, at most 200 characters
question: >-
  What must change in every skill of this repository, and in hal2's autoclear, so that a plan's session only coordinates (every step in a subagent), every step carries Model, Effort and Window sized under 35% of that window, and the coordinator's model, effort and window survive a handoff and clear-and-continue?
status: decided  # planned | researching | verifying | done | decided | abandoned | superseded
answer: >-
  The plan skill makes its session a coordinator that runs every step in one subagent at the row's Model and Effort, with Window and Size columns checked by plan.py (Size at most 35% of Window), keeps its own values in `run: <model> <effort> <window>` synced by the coordinator and /handoff and restored by /handoff c, while hal2's clear-and-continue and restarts take the effort and model from that `run` instead of typing `[autoclear] effort`.
confidence: high  # high | moderate | low
kind: investigation  # decision | investigation | survey | incident | architecture
created: 2026-10-10
updated: 2026-10-10
revisit: 2027-04-10  # when to re-check the answer
author: claude (skills worktree 30)
origin: hal2 farmer brief 2026-10-10-plans-coordinator-only-steps-sized  # shotfiles/<feature>.md#<n>, a plan, or user request
plan: plans/0015-research-plans-coordinator-only-steps-sized/plan.md  # plans/<NNNN>-research-<topic>/plan.md, when a plan ran it
follow_up: [the implementation plan in slot 30]
decision: plans/0015-research-plans-coordinator-only-steps-sized/decisions.md  # INTENT.md row or ADR the outcome went to; empty while undecided
supersedes: []
superseded_by: []
related: []
tags: [plan, handoff, grill, subagents, effort, context-window, autoclear, hal2]
sources: 19
claims: {total: 15, verified: 13, disputed: 0}
---

# Research 0004: Plans coordinator only steps sized

## Answer

A plan's session becomes its coordinator. It runs every step in one subagent at the row's Model and Effort and never in another session. Every row carries Model, Effort, Window and Size, and `plan.py check` refuses a Size above 35% of Window. The coordinator's own values live in the front matter key `run: <model> <effort> <window>`: the coordinator and `/handoff` sync it, `/handoff c` restores it, and hal2 reads it on every clear and restart. **Recommendation: build the implementation plan from the change list under Findings, with D6-D17 as decided. Send hal2 `hal2-changes.md` so that its clear job stops typing `/effort medium` over the plan's level.** Confidence is high: every claim the design rests on comes from code read in both repositories, hal2's own logs or the official Claude Code docs. The two open points (whether a subagent survives `/clear`, and how a slider-set effort shows up) do not change the design.

## Key findings

1. The effort is lost in hal2, not in Claude Code. In pane %10, the clear job typed `/effort medium` over a live `max` at 08:35:15 and again at 08:54:41, because agents.toml sets `[autoclear] effort = "medium"`. `/clear` itself keeps the effort. (confidence: high, hal2's log and the transcripts) [E1][E2][S5][S8]
2. The Agent tool takes `model` (`sonnet|opus|haiku|fable`) and `effort` (`low..max`) but no window. A 5.x model runs with a 1M window by default, and only `CLAUDE_CODE_DISABLE_1M_CONTEXT=1` holds it to 200k. So Window is a sizing budget, not a launch parameter. (confidence: high, the tool schema and the docs) [E3][E4][S6][S14][S15]
3. A general-purpose subagent starts at about 83-84k tokens and a restricted agent at about 35k. A 200k step therefore cannot stay under 35% (70k), while a 1m step leaves about 265k for its work. (confidence: high, measured on this plan's subagents) [E5][S1][S19]
4. hal2's records spec rejects an unknown front matter key, so a `coordinator:` key fails. `run` is a free string, so `run: claude-opus-5-5 max 1m` passes. (confidence: high, checked on a scratch copy) [E6][S1][S13]
5. Nothing checks the Model, Effort or Window of a step today. `plan.py check` delegates to hal2, and hal2's rules check only step numbers and status. (confidence: high, code read) [E7][S1][S10]
6. Every restart (switch, remote-control restart, terminal restore, orphan restart) takes the model and effort from the old process's argv, so a live `/effort` is lost. No servant starter passes `--model` or `--effort`, and `hal2-cli-agents spawn` has no `--effort`. (confidence: high, code read) [E8][E9][S3][S5]
7. hal2 converts `[autoclear] tokens = 300000` to a percent against settings.json's 200k, so on a 1M session the setting never applies. (confidence: high, code read and `settings --json`) [E10][S5]
8. The session's live values can be read without asking. Each main-chain transcript entry carries `effort`, `/effort` writes `Set effort level to <e>`, `$CLAUDE_EFFORT` is set in the Bash tool, and context.py already resolves the model. (confidence: high, checked in this session) [E13][S2][S6]
9. Once a coordinator only waits on subagents, the farmer's `idle-in-plan` (20 min) and sanity-watch's F6 (10 min) would treat that wait as a stop. `hal2-cli-agents list --json` already reports `background_tasks`. (confidence: moderate, code read and earlier false positives in cases.md) [E11][S3]
10. The subservant machinery covers about 60% of parallel.py, two SKILL.md sections, create.py's `--lead` and about 12 farmer places. hal2 slots 31-33 still hold `plans/LEAD`. (confidence: high, code read and live slots) [E12][S1][S3]
11. Outside plan, handoff, grill and the seven session skills, only fix-autoclear's knowledge and the README rows change. (confidence: moderate, a grep-based sweep) [E15][S4]

## Recommendation

The design as decided in [decisions.md](../../plans/0015-research-plans-coordinator-only-steps-sized/decisions.md), D6-D17:

- **Step table** (D6-D8). Columns `| # | Step | Done when | Model | Effort | Window | Size | Status |`, required in every row of a record-format plan, with no fallback to `run`; a legacy plan passes untouched. Model is an alias or a full id (no `[1m]`), Effort `low..max`, Window `200k|1m` (the step's model's window, `1m` for 5.x), Size the step's estimated peak context including the subagent's start of about 85k. `plan.py check` refuses a missing or invalid value and a Size above 35% of Window (rule `plan-steps-sized`).
- **Coordinator values** (D9). `run: <model> <effort> <window>` in the front matter, with no new key. `plan.py new` writes the session's live values, `plan.py run --sync` updates them and `plan.py run --check` compares them.
- **Coordinator loop** (D13). For each step: write `steps/<n>.md`; start one Agent call from `plan.py prompt <n>` (`Plan <NNNN> row <n>: <title>`, the row's model and effort); the subagent edits but never commits; the coordinator runs the done-when, reviews the diff, commits `(plan NNNN step n)`, updates the table, then runs `plan.py run --sync` and `context.py`. Ready steps of a parallel plan go out as parallel Agent calls (Needs and Touches stay). `/mtm milestone` and the Workflow tool stay as step runners.
- **Handoff** (D10). Before a clear the live session wins: `/handoff` runs `run --sync` and commits plan.md. After a clear the plan wins: `/handoff c` runs `run --check` and, when model or effort differ, restarts once through `hal2-cli-agents switch --model --effort --prompt "/handoff c"`. `/handoff clear` passes `--effort` from `run`.
- **Subservants** (D12). No new ones: the plan skill's subservant parts and create.py's `--lead` go. The read-side guards stay until no slot holds `plans/LEAD`: mtm's `subservant-guard.sh`, the farmer's LEAD skips and plan.py's refusal. A follow-up removes them.
- **Starters** (D15). The farmer delegation, fix-loc, sanity-watch and shoot pass explicit `--model` and `--effort`, and their prompts carry one shared coordinator sentence. Defaults are opus medium; fix-loc's coordinator stays on Sonnet.
- **Watchers** (D14). lead_scan's `idle-in-plan` and sanity-watch's idle classes skip a session whose `background_tasks` is not empty.
- **context.py** (D16). The 5.x models count as 1m, `[1m]`-less ids included, unless `CLAUDE_CODE_DISABLE_1M_CONTEXT=1`. It reports the session's values with their sources and the drift against `run`.
- **hal2** (D11, D17), in [hal2-changes.md](../../plans/0015-research-plans-coordinator-only-steps-sized/hal2-changes.md): clear-and-continue and restarts take the effort and model from `run`, then the live level, with `[autoclear] effort` as the last fallback; hal2 never writes plan.md; `[autoclear] tokens` is resolved per session window.

## Decision

Decided 2026-10-10 by the coordinator of plan 0015 under the user's words (D1), in [decisions.md](../../plans/0015-research-plans-coordinator-only-steps-sized/decisions.md) D6-D17. The implementation plan in slot 30 carries them out; hal2's part goes to the hal2 farmer.

---

## Question and scope

The user (D1) wants a plan's session to coordinate only, every step in a subagent sized under 35% of its window, and the coordinator's model, effort and window kept in plan.md across a handoff and clear-and-continue. The trigger was a clear that dropped a `max` coordinator to `medium`. In scope: every skill of this repository, plus hal2's autoclear, read only (D4). Not in scope: changing hal2 from here. Tenets: plans are always correct and checkable (D1), deterministic first, and one home for each value.

## Method

Six read-only subagents ran in parallel (plan 0015 steps 1-6), one per area, and each wrote a findings file. Step 7 (this doc) merges them. The sources were this repository's code and tests, hal2's code at `~/a/hal2/code/rust/`, hal2's state and logs, live `ps` and transcripts, and the docs on code.claude.com. Checks run: a scratch `hal2-cli-records check` for the front matter key, the subagent baselines from transcripts, and `$CLAUDE_EFFORT` and `meta.json` in a subagent. Counts: 6 findings files, 19 sources cited, 15 claims, 13 of them verified locally.

## Background

`run` existed only as the default for empty Model and Effort cells (`plan.py:249-253`). A step's Model and Effort chose the *session*, which restarted through `hal2-cli-agents switch`. Parallel plans used subservant sessions in slots 30-99. context.py guessed 200k for a `[1m]`-less Opus 5.5 that actually ran at 1M (D16).

## Findings

### The plan skill

Details: [findings/plan.md](findings/plan.md). Changes:

- `skills/plan/scripts/plan.py`
  - `steps_table` and `read_steps` (239-284) read `window` and `size`. `run_default` (249-253) returns the model, effort and window, and fills empty cells only in legacy plans (D8).
  - New constants: `MODELS`, `EFFORTS` and `WINDOWS = {200k, 1m}`, and `STEP_SHARE = 0.35`.
  - New `steps_problems(text, slug)` for record plans: Model, Effort and Window are valid in every row, every open row has a Size of at most 35% of its Window, and `run` has three valid words. It is wired into `run_check` (687-732), `check_records` and `describe()['problems']`.
  - New `run <m> <e> <w>`, `run --sync` and `run --check`. `run --check` exits 1 with `{plan, session, switch}`. A legacy plan gets the `Run:` line instead.
  - `new` writes `run` from `context.session_values()` (D9).
  - New `prompt <n>` prints the Agent call's JSON (description, model alias, effort, prompt) and replaces `brief_prompt`. The prompt says: do only `steps/<n>.md`; never edit plan.md, commit or land; report in at most 15 lines.
  - New `migrate [--window 1m]`: it inserts Window after Effort and Size before Status, fills empty Model and Effort from the old `run`, and rewrites `run` from the session. Size stays empty for the next autogrill to fill.
  - Remove `report`, `reports`, `watch` and `assign … slot NN` (57-74, 735-829). Keep `refuse_subservant` (740) and `SUBSERVANT_REFUSES` until the follow-up (D12).
- `skills/plan/scripts/parallel.py`: keep the DAG (`is_parallel`, `parse_needs`, `resource`, `parse_touches`, `kind`, `capacity`, `enrich`, `problems`, `holds`, `schedule`) and, for the guard, `read_marker` and `subservant_marker`. Delete `SUBSERVANT_SLOTS`, `slot_of`, `write_marker`, `worktree_of`, `slot_worktree`, `main_checkout`, `farmer_ledgers`, `farmer_servant`, `slot_taken`, `brief_prompt` (301) and `arrived` (13, 21-26, 173-322). `WHO = lead|subagent|user`.
- `skills/plan/scripts/context.py`
  - `configured_window` (124-129): the 5.x models are 1m unless `CLAUDE_CODE_DISABLE_1M_CONTEXT=1` (D16).
  - New `session_values()` and `--session-values`: model, effort and window, each with its source. Effort: the later of the transcript's last `Set effort level to` and its last main-chain `effort`, then `$CLAUDE_EFFORT` (not inside a subagent), then `--effort` via `$CLAUDE_PID`, then `modelSettings.<id>.effortLevel`. Reuses `session_model` (108-121) and `last_usage` (52). A new `drift` list compares the session with the plan's `run`.
- `skills/plan/SKILL.md`
  - The description drops subservants and `assign`/`brief`/`report`/`reports`/`watch`, and gains coordinator and sized steps. Good steps (58): a step fits one subagent.
  - "Model and effort per step" (207-233) becomes "Model, effort and window per step": the subagent's values, no per-step switch; escalation one effort level up, then a bigger model; the rubric (211-214) links to grill's Auto. `/plan start` (148, 231-233) restarts the session at `run`.
  - Run the plan (245-300; 285-294 today say "implement it") becomes the coordinator loop. Run a parallel plan (301-411) shrinks to about 15 lines. Delete Work as a subservant (412-434), lines 53-56 and rows 153-158.
  - Finish a step (454-): `run --sync` before `context.py`; the clear passes `--effort` from `run`.
- `skills/plan/templates/`: `plan.md` gets `run: <model> <effort> <window>`, the note at 29-30 ("Model, Effort, Window are the subagent's, Size its peak, at most 35% of Window; `run` is the coordinator's") and Window and Size in the table at 32-35; `step.md` gets `Size: <n>k of <window>`; delete `step-brief.md` and `report.md`; `handoff.md` is unchanged.
- Tests: adapt `test_plan.py:91,104` and `test_folder.py:64-83`; delete `test_parallel.py:199-348,361-419` except the `ready` and `who` checks; add tests for `prompt`, `steps_problems` (missing, invalid and oversize values; legacy exempt; `run` without a window), `run`, `migrate`, and context.py's `session_values` and `drift`.

### Handoff and grill

Details: [findings/handoff-grill.md](findings/handoff-grill.md). Changes:

- `skills/handoff/SKILL.md` Write (100-): a new "### 3b. Persist the coordinator's values", `plan.py run --sync` before `where.py --stamp`; step 5 (307-) commits plan.md with the docs through `commit-handoff.sh` (74-95).
- `skills/handoff/SKILL.md` Continue (39-99), a new step 0: `plan.py run --check`; if model or effort differ, `hal2-cli-agents switch --model --effort --prompt "/handoff c" --detach --json` and end the turn. Loop guard: if a switch already ran for this handoff's `at`, run `run --sync` instead. A refused switch (exit 3): go on and note it under Watch out. Never `--sync` before step 0.
- `/handoff clear`: `hal2-cli-agents clear-and-continue --effort <run's effort> --detach --json`.
- `skills/grill/SKILL.md` `## Auto` (67-82), a new point "Size every step": every row gets Model, Effort, Window and Size by the rubric in findings/plan.md (about 12 tokens a line read, 1.5× the changed text, 1-15k per test run, 3-5k fixed). Size includes the subagent's start (D7); a row over 35% is split along its files or checks.
- Tests: `skills/handoff/scripts/test_record.py` (`run --check` exits 1 on a differing session; after `--sync` the commit holds the new `run`), and a test that greps SKILL.md for step 0 coming before any `--sync`.

### The skills that start sessions

Details: [findings/session-skills.md](findings/session-skills.md). Changes:

- **One coordinator sentence** in `skills/plan/templates/coordinator-rule.md` (or `plan.py coordinator-rule`), included by every starter: "You are this plan's coordinator: never do a step yourself; run every step in a subagent at its Model and Effort, never in another session; every row carries Model, Effort, Window and Size under 35% (`plan.py check` passes)."
- `skills/create-worktree-session/`
  - Delete `--lead`, `--base`, `create_worktree`, `leftover`, `lead_parts` and `write_lead`: `create.py:5,15-21,106-112,115-132,141-153,156-196,242-248`, `SKILL.md:3,18-20,26-31` and `test_create.py:141-208`.
  - Keep `--from` (doc "servants: `--from 30`") and `--exact`.
  - The JSON echoes the model and effort. There is no `--window` (D6).
- `skills/farmer/`
  - The prompt (`scripts/delegation.py:32-40`, `templates/SERVANT-ROLE.md:13-14`, `reference.md:134-142`) gets the sentence. `delegation.py:108-128` passes `--model` and `--effort` from the ROLE settings `servant_model` and `servant_effort` (default opus medium) and switches a reused session whose values differ; `delegate()` (149-172) logs them.
  - `instructions/mtm.md:19`: the orphan restart passes the plan's `run`. `lead_scan.py:111-114` `classify()` skips sessions with live `background_tasks` (D14).
  - The 30-99 rule's reason (`SKILL.md:145-147`, `reference.md:126-130,161-163`, `delegation.py:6-8,29`) loses its subservant comparison; `reference.md` gets a `servant_limit` note.
  - Follow-up (D12): remove `lead_marker.py`, `lead_scan.py:106-112,138-144`, `duties.py:40-42,77-81`, `mtm_scan.py:147-158,225-251,294-296,314-323`, `boss.py:138-171`, `trains.py:65-70,215`, `prune.py:15-23,59-61,129,147-170,288,352-361`, the instruction and subskill lines, and the tests listed in the findings.
- `skills/sanity-watch/`
  - The fix-agent prompt (`SKILL.md:156-170`) gets the sentence and sized rows (the test and the fix at opus high 1m, the logs and uat at sonnet medium 1m). The start (148-153) changes to `create.py --from 30 --model --effort`.
  - `scan.py` F6 (283-292) skips live `background_tasks`; F7 (293-299) counts an `Agent` call whose subagent transcript moves as waiting; a new class covers a dead subagent with an idle parent (`cases.md:26-42`). The resume prompt (`SKILL.md:84`, `farmer/instructions/watch.md:11`) says "as its coordinator".
- `skills/fix-loc/`: `servant-prompt.md:1` gets the sentence and sizing (step defaults sonnet medium 1m). `loop.py:28,114,150-170` and `tick.py:3` get `--coordinator-model` (Sonnet, D15), `--coordinator-effort` and `--step-model`, kept in `state.json`; the start runs `create.py --from 30`. `SKILL.md:8` says "loop session" instead of "coordinator".
- `skills/shoot/` and `skills/digest-todolist-picture/scripts/implement.py`: the sentence goes in `shoot/SKILL.md:127-135` and `implement.py:29-44` (item 7 at :41); `implement.py:170` and `SKILL.md:82,94-99` pass the model and effort; a reused session (`SKILL.md:83`) is switched first. hal2-nvim's `shot-template-single.md` item 7 goes to the hal2 farmer.
- `skills/mtm/`: `SKILL.md:30-35` says a landing runs only in the coordinator, never in a subagent. Milestone mode (`SKILL.md:59,79-93`, `references/ci.md:48-51`) says "a plan's coordinator". `subservant-guard.sh`, its bats test and `SKILL.md:62-69` stay until the follow-up.
- `skills/research/`: `SKILL.md:25-30` gives the research plan sized rows; quick mode (112-120) has a subagent write `research.md`; the Workflow (72-75) stays a step runner (D13). `workflows/deep-research.js:55-61,122-129,138,217,278` sets a model per role if `agent()` takes one.

### The other skills

Details: [findings/other-skills.md](findings/other-skills.md). Changes:

- `skills/fix-autoclear/SKILL.md:147,157,171-177,203` and `cases.md`, after hal2's change: the effort comes from the plan's `run`, then the live level, then `[autoclear] effort`; the busy-path note (157) is updated; the `/effort` settings.json trap is kept.
- `README.md`: line 12, the plan row drops "subservants in slots 30-99" and gains sized steps; line 11, the handoff row says it persists and restores `run`; lines 16-17 and 29 checked.
- Optional: `continue/SKILL.md:40,55` and `pause/SKILL.md:27,60-69` need nothing, because the plan holds `run`.
- No change in every other skill and repository file (table in the findings).

### hal2

Details: [findings/hal2.md](findings/hal2.md); the brief: [hal2-changes.md](../../plans/0015-research-plans-coordinator-only-steps-sized/hal2-changes.md). hal2 (1) restores effort and model from `run` in the clear job, guard and sweep (`autoclear.rs:1427-1431`, `autoclear/effort.rs`, `main.rs:438`, `guard.rs:745-756`, `sweep.rs:357`); (2) reads `run` on restarts (`restart/replace.rs:86-95`, `restore.rs:57-58,70-76`); (3) adds `spawn --effort` (`apps/hal2-cli-agents/src/lib.rs:42`); (4) resolves `tokens` per session window (`settings.rs:274-285,325-334`, `guard.rs:598`); (5) optionally displays Window, Size and `run` (`plan_steps.rs`, `document.rs`). The findings' draft key `coordinator:` is replaced by `run` (D9).

### Claude Code

Details: [findings/claude-code.md](findings/claude-code.md). Nothing in Claude Code changes. For the skills: every step's Agent call passes `model` (the alias) and `effort`, the plan skill's rule being the instruction the schema asks for; never set `CLAUDE_CODE_EFFORT_LEVEL`, which pins every subagent's effort too; `/effort <level>` (not `max`) rewrites settings.json, so a restore goes through `switch --effort`, never a typed `/effort`; whether a running subagent survives `/clear` is unproven, so the coordinator clears only at a step boundary, after its subagents have reported.

## Options

- **35% budget, whole context (chosen, D7)** against **work above the subagent's start** (findings/plan.md, handoff-grill.md) or a **lean agent type** of about 35k. "Whole context" is what fills the window and what a transcript measures. "Above the start" would let a step use 70k of work on a 200k window that already holds 85k. A lean agent cuts the start but loses the MCP tools.
- **`run` key (chosen, D9)** against a new **`coordinator:` key** (findings/hal2.md's draft) or a line in handoff.md. hal2's spec rejects `coordinator:` unless hal2 changes its schema first. handoff.md is not read by restarts.
- **Keep the subservant guards for now (chosen, D12)** against **deleting them with the subservant code**. Slots 31-33 still carry `plans/LEAD`, so deleting the guards could let a stale slot land.
- **Window as a budget (chosen, D6)** against **Window as a launch flag** (create.py `--window`, a `[1m]` suffix). The Agent tool takes no window, and the 5.x models are already 1M.
- **Size as a table column (chosen, D8)** against a line in `steps/<n>.md`. A column is checkable before the step is next.
- **Effort restore from the plan, then the live level (chosen, D11)** against **the live level only** or **dropping `[autoclear] effort`**. The live level is lost on a restart, and dropping the key ends the user's 2026-10-06 wish for sessions without a plan.

## Comparison

| Criterion | Whole context (D7) | Above start | Lean agent |
|---|---|---|---|
| Measures what degrades a step | yes | no | yes |
| Works with 200k steps | no (start is 42%) | yes | yes |
| Keeps MCP tools in steps | yes | yes | no |

| Criterion | `run` (D9) | `coordinator:` | handoff.md line |
|---|---|---|---|
| Passes hal2's spec today | yes | no | yes |
| Read by hal2 on restart | yes, after the change | yes, after the change | no |
| One home for the value | yes | yes | no (two files) |

| Criterion | Guards kept (D12) | Guards deleted now |
|---|---|---|
| A stale `plans/LEAD` slot can land | no | yes |
| Dead code until the follow-up | about 12 farmer places | none |

## Assumptions and what would change our mind

- Assumes the 5.x models keep a 1M default. Signpost: Claude Code changes its default window, or adds a window parameter to the Agent tool.
- Assumes about 85k for a subagent's start. Signpost: a lean `.claude/agents/plan-step.md` lands, so the rubric's start drops.
- Signpost: hal2's spec allows extra keys. A dedicated `coordinator:` key could then replace `run`.

## Risks

- Premortem: a year later the coordinator still lost its effort because a restart path that `hal2-changes.md` did not name (a new starter) read argv only. Counter: the contract is "every restart reads `run` when the worktree has a current plan", tested per path.
- A coordinator cleared while subagents ran loses them. The loop clears only at step boundaries.
- `migrate` misjudges sizes. Size stays empty after `migrate`, and the next autogrill fills it.

## Open questions

- Does a running background subagent survive `/clear`? Test it once in a scratch session. Until then, clear only at step boundaries.
- Does a slider-set effort (the `/model` slider, Remote Control) show in the transcript or in `$CLAUDE_EFFORT`? Set it once and read both.
- Does the Workflow `agent()` take a model and effort per role? Read the Workflow API, then set it in deep-research.js.

## Next steps

- The implementation plan in slot 30, built from the Findings change list. It lands this plan with it (D2).
- `hal2-changes.md` goes to the hal2 farmer. The follow-up that removes the subservant guards starts once `find ~/.hal/git/worktree -path '*/plans/LEAD'` is empty.

## Evidence

| ID | Claim | Sources | Type | Verified | Confidence |
|---|---|---|---|---|---|
| E1 | hal2 typed `/effort medium` over `max` in pane %10 at 08:35:15 and 08:54:41 | S5, S8, S9 | log | yes | high |
| E2 | `/clear` keeps the effort (the screen showed `max` after the clear) | S5, S6, S8 | log | yes | high |
| E3 | The Agent tool takes a model alias and an effort, no window | S6, S14 | schema, doc | yes | high |
| E4 | 5.x models run 1M by default; 200k only under `CLAUDE_CODE_DISABLE_1M_CONTEXT` | S6, S15 | doc, session | yes | high |
| E5 | A general-purpose subagent starts at about 83-84k tokens, a restricted one at about 35k | S1, S2, S19 | measured | yes | high |
| E6 | hal2's spec rejects an unknown front matter key; `run` passes | S1, S13 | test run | yes | high |
| E7 | No check looks at Model, Effort or Window | S1, S10 | code | yes | high |
| E8 | No starter passes `--model`/`--effort`; `spawn` lacks `--effort` | S3, S5 | code | yes | high |
| E9 | Restarts read model and effort from the old argv only | S5, S12 | code | yes | high |
| E10 | `[autoclear] tokens` is resolved against settings.json's 200k | S5, S12 | code, CLI | yes | high |
| E11 | Idle scans would flag a coordinator waiting on subagents | S3 | code, cases | partly | moderate |
| E12 | Slots 31-33 of hal2 still hold `plans/LEAD` | S3 | live state | yes | high |
| E13 | The transcript and `$CLAUDE_EFFORT` give the live effort | S2, S6 | session | yes | high |
| E14 | `/effort <level>` (not `max`) saves to settings.json | S5, S6, S15 | doc, settings | yes | high |
| E15 | Only fix-autoclear and README change outside the named skills | S4 | grep | partly | moderate |

## Sources

- [S1] Findings: the plan skill — plan 0015 step 1. [findings/plan.md](findings/plan.md)
- [S2] Findings: handoff and grill — plan 0015 step 2. [findings/handoff-grill.md](findings/handoff-grill.md)
- [S3] Findings: the skills that start sessions — plan 0015 step 3. [findings/session-skills.md](findings/session-skills.md)
- [S4] Findings: other skills — plan 0015 step 4. [findings/other-skills.md](findings/other-skills.md)
- [S5] Findings: hal2 — plan 0015 step 5. [findings/hal2.md](findings/hal2.md)
- [S6] Findings: Claude Code — plan 0015 step 6. [findings/claude-code.md](findings/claude-code.md)
- [S7] Decisions of plan 0015, D1-D17. [decisions.md](../../plans/0015-research-plans-coordinator-only-steps-sized/decisions.md)
- [S8] hal2 autoclear log of pane %10 (`~/a/dev`), `~/.local/state/hal2/agents/autoclear/10.log`, 2026-10-10.
- [S9] `~/.config/hal2/agents.toml` `[autoclear]` (`effort = "medium"`, `tokens = 300000`), read 2026-10-10.
- [S10] This repository: `skills/plan/scripts/plan.py`, `parallel.py`, `context.py` and `templates/`, at 094df8f.
- [S11] This repository: `skills/handoff/SKILL.md`, `skills/grill/SKILL.md`, at 094df8f.
- [S12] hal2: `code/rust/libs/hal2-agents/src/` `autoclear.rs`, `autoclear/effort.rs`, `guard.rs`, `sweep.rs`, `settings.rs`, `restart/replace.rs`, `restore.rs`; `apps/hal2-cli-agents/src/main.rs`, `lib.rs`.
- [S13] hal2: `code/rust/libs/hal2-records/specs/plan.toml` and `hal2-cli-records schema plan`.
- [S14] Subagents — Anthropic. https://code.claude.com/docs/en/sub-agents.md (accessed 2026-10-10)
- [S15] Model configuration — Anthropic. https://code.claude.com/docs/en/model-config.md (accessed 2026-10-10)
- [S16] Environment variables — Anthropic. https://code.claude.com/docs/en/env-vars.md (accessed 2026-10-10)
- [S17] Status line — Anthropic. https://code.claude.com/docs/en/statusline.md (accessed 2026-10-10)
- [S18] Hooks — Anthropic. https://code.claude.com/docs/en/hooks.md (accessed 2026-10-10)
- [S19] Plan 0015's subagent transcripts and `agent-*.meta.json`, `~/.claude/projects/-Users-mod--hal-git-worktree-skills-30/`, 2026-10-10.

## Log

- 2026-10-10: created; findings of steps 1-6 written; synthesized by step 7 with decisions D6-D17, status decided.

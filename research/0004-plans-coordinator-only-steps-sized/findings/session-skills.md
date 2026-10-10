# Findings: the skills that start sessions or write plans

Step 3 of plan 0015. Read: farmer, create-worktree-session, sanity-watch, fix-loc, shoot (with
digest-todolist-picture's `implement.py`), mtm, research. Paths are relative to `skills/`. Live state read on 2026-10-10.

## Summary

1. No servant prompt says "coordinator": the farmer, sanity-watch, fix-loc and shoot all say "create the plan ... run it to its end". None of them requires Model, Effort or Window per step.
2. Subservants are wired into the farmer in about 12 places: `lead_marker.py`, plus branches in boss, mtm_scan, trains, prune, lead_scan and duties, four instruction files and two subskills. They are also in create.py (`--lead`, `--base`) and mtm (`subservant-guard.sh`, milestone mode). All of it can go, but only after hal2's live subservant slots are gone (Migration).
3. The servants are started inconsistently. The farmer uses create.py from slot 30 and passes no model and no effort. fix-loc uses `hal2-cli-agents spawn` from slot 01 with Sonnet and no effort. sanity-watch uses `spawn` from slot 01 with neither. shoot uses create.py from slot 01 with neither. None passes a window: hal2 has no window flag, and the window is part of the model id (`opus` = `opus[1m]`).
4. With a coordinator-only design, idle-while-subagents-run becomes the normal state. Today it reads as a stop: lead_scan's `idle-in-plan` fires after 20 min, sanity-watch's F6 after 10 min, and F7 fires on a long foreground Agent call. `hal2-cli-agents list --json` already has `background_tasks`, which the scans should use.
5. The starters cannot take coordinator values from the plan, because the servant writes the plan after it starts. Instead, each starter passes explicit coordinator values. `plan.py new` records the values the session actually runs at. Every restart (orphan, restore, switch) then reads them back from plan.md.

## Findings per skill

### create-worktree-session

- `SKILL.md:3,18-20,26-31` and `create.py:5,15-21` describe the subservant mode. The `--lead` code is at `create.py:156-196` (`create_worktree`, `lead_parts`, `write_lead`) and `create.py:242-248`. `--base` is at `create.py:106-112,115-132,141-153`. The tests are at `test_create.py:141-208`. The only callers of `--lead` and `--base` are in the plan skill's lead loop (`plan/SKILL.md:359-365`). **Change:** remove `--lead`, `--base`, `create_worktree` and `leftover`, along with their tests and doc rows. Nothing else uses them. **Why:** subservants go away (design a).
- `--from` (`SKILL.md:18`, `create.py:239-244`) has one caller: the farmer (`farmer/scripts/delegation.py:121`). **Keep it.** Rewrite its doc as "servants: `--from 30`" and drop "subservants".
- `--model` and `--effort` (`SKILL.md:16`, `create.py:205-208`) are passed through to `hal2-cli-git worktree run`. There is no window flag. **Change:** add `--window 200k|1m`, which maps to the model id (the `[1m]` suffix or none; the exact mapping is step 6's). Echo `model`, `effort` and `window` in the JSON, so callers can log the coordinator values they started.
- `--exact` (`create.py:224-227`) is used by `implement.py:170`. Keep it.

### farmer

- **The servant prompt.** It is in `scripts/delegation.py:32-38` (PROMPT), `:39-40` (PLAN_TASK), `templates/SERVANT-ROLE.md:13-14` (`{task}`) and `reference.md:134-142` (the prompt written out by hand). All of them say "Create the plan ... Then run the plan to its end. It lands itself." **Change:** add the coordinator rule, and require the step columns. **Why:** this is the user's own requirement: the agent that creates and runs a plan must be told it is the coordinator.
- **The start parameters.** `delegation.py:108-128` reuses an idle free session in slots 30-99 as it is, and types the prompt into it. Otherwise it runs `create.py --repo --from 30 --prompt`, with no `--model` and no `--effort`. `reference.md:161-162` says servants "run the same model as the user's servants (create-worktree-session's default)". **Change:** pass the coordinator values explicitly. Before typing into a reused session whose values differ, run `hal2-cli-agents switch`. Record `model`, `effort` and `window` in `delegations.jsonl` (`delegate()`, `:149-172`).
- **The direct-task servants** (`role_sync.py:18-27`, "No plan for this") run no plan, so the coordinator rule does not apply. The fix-autoclear delegation (`duties.py:178-179`, `text=/fix-autoclear <slot>`) inherits whatever fix-autoclear's plan does (step 4).
- **`servant_limit`** (`reference.md:16-17,117-118`, `delegation.py:131-146`) counts sessions. Each coordinator now runs subagents at the same time, and their builds and tests run on this Mac, so one servant puts more load on the machine than before. The `auto` setting (load1 per core < 0.8) adapts by itself. A numeric limit does not, and may need to be lower (note it in `reference.md`). The ledger and the follow-up (`delegation.py:175-198`) need no change.
- **The 30-99 rule** (`SKILL.md:145-147`, `reference.md:126-130,161-163`, `delegation.py:6-8,29`) is justified there by "like a parallel plan's subservants". **Change:** keep servants in slots 30-99, but justify it as the user's helper-slot rule and drop the comparison to subservants.
- **Subservant handling. Remove it after the migration:**
  - `lead_marker.py` (the whole file);
  - `lead_scan.py:106-112,138-144`;
  - `duties.py:40-42,77-81` (`continue-step`);
  - `mtm_scan.py:147-158,225-251,294-296,314-323`;
  - `boss.py:138-171`;
  - `trains.py:65-70,215`;
  - `prune.py:15-23,59-61,129,147-170,288,352-361`;
  - `instructions/lead.md:13,16-21`, `mtm.md:21-30`, `prune.md:16-20`, `trains.md:5`;
  - `subskills/merge-train/SUBSKILL.md:19`, `subskills/merge-to-main-boss/SUBSKILL.md:60`;
  - `SKILL.md:38` (the prune row), `:147`, and `reference.md:149-150,179-184`;
  - the tests: `test_boss.py:65-83,162-182`, `test_duties.py:37-53`, `test_lead_scan.py:50-139`, `test_mtm_scan.py:180-248,332-339`, `test_prune.py:211-293`, `test_trains.py:72-79` and `test_delegation.py:114-137`.
- **A coordinator waiting on subagents.** `lead_scan.py:111-114` (with `IDLE_IN_PLAN_AFTER = 20 min`, `:36`) reports `idle-in-plan` for any idle session that has a plan. `duties.py:39` then sends "Continue the plan to its end" whenever the last line matches `GOING_ON` (for example "Now I'll wait for…"). **Change:** `classify()` skips sessions whose `background_tasks` (from `hal2-cli-agents list --json`) are non-empty and alive. **Why:** otherwise every coordinator gets nudged while its subagents run.
- **Restarts lose the coordinator values.** The orphan restart in `instructions/mtm.md:19` runs `hal2-cli-git worktree run <NN> --agent claude --detach --prompt "/handoff c"` with no model or effort. **Change:** read the plan's coordinator values (`plan.py current` → `run`) and pass `--model`, `--effort` and the window. This is design (c).

### sanity-watch

- **The fix-agent prompt** (`SKILL.md:156-170`) reads: "Create the fix plan with `plan.py new ... --autogenerated sanity-watch` ... Its steps must include: regression test, logs, fix, uat ... run the plan with /plan n to its end". It has no coordinator rule and no step sizes. **Change:** add both. Every one of the four required steps carries Model, Effort and Window. Suggested defaults: the regression test and the fix at opus high 200k, the logs and uat at sonnet medium 200k. `plan.py check` must pass before `plan.py grilled`.
- **The spawn** (`SKILL.md:148-153`) runs `hal2-cli-agents spawn <project> --json --prompt`. That takes the lowest slot from 01 that has no live agent, even one that still holds work, and passes no model and no effort. The farmer's watch duty uses `farmer.py delegate` instead (`farmer/instructions/watch.md:17-18`). **Change:** start through create.py with `--from 30 --model --effort --window` (the coordinator values), like the farmer's servants.
- **Scan false positives** become the normal case:
  - F6 (`scripts/scan.py:283-292`, `EARLY_END_AFTER = 10 min`, `:41`) flags any idle session whose plan has a next step. `cases.md:70-85` already records five false positives for "waiting on its own background task".
  - F7 (`scan.py:293-299`, `HANG_AFTER_IN_TOOL = 60 min`) would flag a coordinator blocked in a long foreground Agent call.

  **Change:** skip F6 while `background_tasks` is non-empty and alive. Treat a PreToolUse on `Agent` as waiting, not hanging, as long as the subagent's transcript moves. Add the class that `cases.md:26-42` proposes: a background subagent dead (SubagentStop) but still listed, with its parent idle. Under this design that is a stuck coordinator.
- **The F6 resume prompt** (`SKILL.md:84`, and `farmer/instructions/watch.md:11`) says "Continue the plan to its end". **Change:** add "as its coordinator: start step <n> in a subagent at its Model/Effort/Window".

### fix-loc

- **The servant prompt** (`servant-prompt.md:1`) reads: "Its steps, one per group of related files ... then run the plan with /plan n to its end". It has no coordinator rule and no sizing. **Change:** add the coordinator rule. Steps are cut so that each one's reads and writes stay under 35% of its window. Every step carries Model, Effort and Window, defaulting to `sonnet medium 200k`.
- **The start** (`SKILL.md:25,67-68`; `scripts/loop.py:28,150-170`, command at `:157`) runs `hal2-cli-agents spawn <checkout> --model claude-sonnet-5-5 --json --prompt`: slot 01 and up, no effort, no window. The model is stored at `loop.py:114,166` and `tick.py:3`. Today the Sonnet session does the work itself. **Change:** split `--model` into two settings:
  - `--coordinator-model/--coordinator-effort`, which start the session;
  - `--step-model` (default sonnet), which the prompt tells the servant to use in its rows.

  Start through create.py `--from 30` (helper slots, no slot that holds work). Store all of the values in `state.json`.
- **A naming clash.** `SKILL.md:8` calls fix-loc's own loop session "A coordinator". **Change:** call it the "loop session" there. **Why:** "coordinator" will mean a plan's session.

### shoot (and implement.py)

- **The shot template** (`digest-todolist-picture/scripts/implement.py:29-44`, item 7 at `:41`: "Make this shot a plan ... then carry it out") has no coordinator rule. The real template is `shot-template-single.md` in hal2-nvim's `templates/`; it is not in `~/.config/hal/util/shooter/nvim/`. The same applies to `shoot/SKILL.md:127-135` ("Make every shot a plan ..., then carry the plan out"). **Change:** "...then run it as its coordinator: every step in a subagent at its Model/Effort/Window". Change the fallback here, and send the template change to hal2.
- **The start** (`SKILL.md:82,94-99`, `implement.py:170`) runs `create.py --repo --prompt --exact` with no model and no effort. The "free session" option (`SKILL.md:83`) types the prompt into an existing session as it is. **Change:** pass the user's default coordinator values. When reusing a session, `switch` it first if its values differ.

### mtm

- **The guard.** `SKILL.md:3,62-69`, `scripts/subservant-guard.sh:1-42` and `test_subservant_guard.bats` refuse to land a slot marked `plans/LEAD`. **Change:** keep the guard until the last marked slot is pruned, then delete the script, its test and `SKILL.md:62-69`.
- **Milestone mode.** `SKILL.md:59,79-93` and `references/ci.md:48-51` describe `/mtm milestone`, which only "a parallel plan's lead" runs. **Change:** if the plan skill keeps milestone rows (step 1), reword it to "a plan's coordinator". Otherwise remove it.
- **Who lands** (`SKILL.md:30-35`): a plan's landing is run by "the plan skill's Land the plan" in the session the user started. **Change:** add one line: a landing (`/mtm`, also `/mfm`) runs only in the coordinator's session, never in a step's subagent. **Why:** a subagent cannot receive the boss's messages, and must not hold the queue past its own end.

### research

- **The research plan** (`SKILL.md:25-30`): "Every research runs under a plan ... its steps are this skill's steps." Nothing makes those steps carry Model, Effort or Window, or keeps the coordinator from running them itself. The Workflow (`SKILL.md:72-75`) and quick mode (`:112-120`, 1-3 subagents, with the coordinator writing `research.md` itself) both have the session doing the work. **Change:** `/research` writes its plan with sized rows. For example:
  1. scope and scaffold: sonnet medium 200k;
  2. research (Workflow or subagents): see Open questions;
  3. write `research.md`: opus high 200k;
  4. check and close: sonnet low 200k.

  The coordinator only starts these and judges the results.
- **The workflow's agents.** In `workflows/deep-research.js:55-61,122-129,138,217,278`, `agent()` sets no model or effort, so every agent inherits the session's. **Change:** if the Workflow API accepts it, set the model per role. Suggested: planner and report at opus, researchers and verifiers at sonnet.

## Proposed changes

| File, place | New text or behaviour |
|---|---|
| `farmer/scripts/delegation.py` PROMPT, PLAN_TASK; `templates/SERVANT-ROLE.md` Your task; `reference.md:134-142` | Replace "Then run the plan to its end." with: "You are this plan's coordinator: never do a step yourself; run every step in a subagent (Agent tool) at the step's Model and Effort, never in another session. Every step row carries Model, Effort and Window, cut to stay under 35% of that window (`plan.py check` passes). Then run the plan to its end; it lands itself." |
| shared constant | Put that sentence in one place, e.g. `plan/templates/coordinator-rule.md` or `plan.py coordinator-rule`. delegation.py, sanity-watch, fix-loc's `servant-prompt.md`, `implement.py`'s FALLBACK and the hal2-nvim template all include it, so a wording change happens in one file. |
| `delegation.start()` | Add `--model/--effort/--window` from new ROLE.md settings `servant_model`, `servant_effort` and `servant_window`. Default: the user's default `opus medium`; the window is open (Q below). When reusing a session, compare its model and effort (`hal2-cli-agents list`) and `switch --model --effort --prompt <prompt> --detach` if they differ. Log the values in the ledger. |
| `create-worktree-session/scripts/create.py` | Delete `--lead`, `--base`, `create_worktree`, `leftover`, `lead_parts` and `write_lead`, and their tests. Add `--window`. Add `model`, `effort` and `window` to the JSON. Update the SKILL.md description and table. |
| `sanity-watch/SKILL.md` §4 | Start with `python3 <K>/create-worktree-session/scripts/create.py --repo <project> --from 30 --model <m> --effort <e> --window <w> --prompt ...`. Add the coordinator sentence and the default step values to the prompt. |
| `sanity-watch/scripts/scan.py` F6/F7, `farmer/scripts/lead_scan.py` classify | A live `background_tasks` entry means "waiting", not "stopped". Add a new class for a dead subagent (SubagentStop) whose parent is idle: resume the coordinator with "your subagent for step <n> ended without a report; check its result and go on". Add tests for both. |
| `fix-loc/scripts/loop.py`, `servant-prompt.md`, SKILL.md | `--coordinator-model/--coordinator-effort/--window` and `--step-model` (default sonnet). Start through create.py `--from 30`. Add the sizing and coordinator text to the prompt. Rename "coordinator" in SKILL.md:8 to "loop session". |
| `shoot/SKILL.md:127-135`, `implement.py:41,170` | Add the coordinator sentence. create.py gets the coordinator values. Ask the hal2 farmer to change hal2-nvim's `shot-template-single.md` item 7. |
| `farmer/instructions/mtm.md:19` (orphan restart) | `--model/--effort` from `plan.py current`'s coordinator values. Never a bare `worktree run`. |
| `mtm/SKILL.md` | Add "a landing runs in the coordinator, never in a subagent". Milestone mode moves to "a plan's coordinator", or goes (step 1). Remove the guard after the migration. |
| `research/SKILL.md` §plan, quick mode; `deep-research.js` | Sized rows for the research plan. The coordinator does not write the doc. Set the model per agent role where the API allows. |
| farmer subservant code (list above) | Phase 2, once no `plans/LEAD` slot is left: delete the code with its tests. Keep `prune.py`'s marked-slot removal until then. |

## Open questions

- Window for coordinators. hal2 maps `--model opus` to `opus[1m]`, which is the user's default. Should a coordinator get the 1m window (it reaches 35% later, so fewer handoffs, but costs more per turn) or 200k? Steps 5 and 6 say how 200k is requested for an alias.
- Coordinator effort. The user's default is medium (`plan/SKILL.md:216`). Is that enough to judge the reports, or should servants that coordinate run at high?
- fix-loc. Should the coordinator stay Sonnet, which is cheap but judges the splits, or be Opus with Sonnet steps?
- The Workflow tool. May a subagent run it, and does the Workflow `agent()` take a model and effort? If neither, does running a Workflow from the coordinator count as "a step in subagents"? This is Claude Code's part (step 6).
- `/mtm milestone`. Does the plan skill keep milestone rows for long coordinator-only plans (step 1)?

## Migration

- **What runs now** (2026-10-10, read only). hal2 slots 31, 32 and 33 carry `plans/LEAD` = `02 0149-hal9k-the-whole-roadmap-in-one-plan`, for steps 370, 164 and 160; the markers were written on 2026-10-09 around 17:23. No agent runs in them now. 31 and 32 hold nothing that `origin/02` lacks. 33 has 2 uncommitted files. The lead is hal2 slot 02 (state `sleeping`), running plan 0149: a 2273-line parallel plan with subservants and milestones.
- **Order:**
  1. Ship the new create.py flags and the prompts first. Keep `--lead` working, but stop the plan skill from calling it (step 1).
  2. Tell the hal2 farmer to have plan 0149's lead convert its open rows: Who becomes a subagent, Window is added, oversized rows are split. It merges 31 and 32 (nothing is missing), and has slot 33's 2 uncommitted files either committed and reported or dropped. The prune duty then removes 31-33 (`prune.py` marked-slot path).
  3. Once `find ~/.hal/git/worktree -path '*/plans/LEAD'` finds nothing in any repo, delete the subservant code (phase 2 above), `subservant-guard.sh` and `--lead`.
- **Other running plans.** Plans that already exist have tables without a Window column, and `plan.py check` will refuse them. They need a one-time `plan.py migrate` (step 1), run by each plan's coordinator at its next `/handoff c`. Servants already running (`delegations.jsonl` entries in state `running`) finish under the old prompt. Only new delegations get the new one.

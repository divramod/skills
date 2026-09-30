---
name: fix-autoclear
description: Analyze and fix a failure of hal2's autoclear (the context guard, the clear-and-continue job and the sweep that hand off, /clear and continue a plan-running Claude session at the context threshold) — from the worktree it happened in (`/fix-autoclear 02`; screenshots optional, the pane's screen is captured read-only) or a shot hal2 reported in the global `fix-autoclear` shotfile. Collects the evidence (job record and log, guard markers, the session's transcript tail, the sweep's log), matches it against known failure cases, finds the root cause in hal2's code, fixes it with a regression test replaying the incident, installs the fix, gets the stuck session going again and records the case so the skill learns. `/fix-autoclear doctor` looks for autoclear failures nobody reported; `/fix-autoclear selfcheck` checks this skill's insider knowledge against the code. Use when the user says /fix-autoclear, "autoclear did not work / is stuck / did not continue", or shows a pane stopped by `hal2 stopped this turn` / `stopped for the hand-off`. `/fix-autoclear h` shows help.
---

# fix-autoclear

The user names the agent (`02` or `hal2 wt 02`, a few words on what it did instead; screenshots optional), or hal2
reported the failure itself as a shot in the global shotfile `fix-autoclear` (`<repo> wt <NN>: <reason>`, with the
command to run). Name agents by repository and worktree (`hal2 wt 02`), never by pane id. You find
why hal2's autoclear did not hand off, clear and continue, fix it in hal2 and make the case known to this skill.
`S=<skill-dir>/scripts`, `E="python3 $S/evidence.py"`. Ask every question with the question tool, recommended
option first.

| Call | Does |
|---|---|
| `/fix-autoclear <worktree> [<description>]` | analyze one incident (`02`, `main`; `--repo <name>` outside that repo) and fix it |
| `/fix-autoclear doctor [<hours>]` | list autoclear failures of the last hours (default 24) nobody reported, offer to analyze each |
| `/fix-autoclear selfcheck` | check the insider knowledge below against hal2's code; fix the drift |
| `/fix-autoclear h`, `/fix-autoclear help` | print this table and stop |

## 1. Collect the evidence

1. `$E show --worktree <NN> [--repo <name>] [--hours 3]` (or `--pane`, `--session` when the agent is gone) prints
   the settings and installed binary, the agent now, **its screen** (captured with `hal2-cli-agents capture`,
   read-only: never type into the pane), the pane's job record and job log, the guard markers of its sessions, each session's transcript
   tail (tools, hook denials, typed requests), the guard's decisions (`guard.log`), the sweep's rounds for the pane
   (`sweep.log`) and hal2-api's sweep lines. A missing tool exits 2: run
   `bash $S/install-prerequisites.sh`.
2. Read the screen (and screenshots when the user gave some): the pane's last lines (the hook denial, `hal2
   stopped this turn ...`, `Interrupted`, the input box, a dialog), the statusline (context %, plan).
3. `$E doctor --hours 6` shows whether other panes failed the same way.
4. Build the **timeline**: soft stop → what the model did → hard stop? → job phases → sweep ticks → where it
   stopped. The failure is the first step that did not do what the insider knowledge below says it does.

## 2. Match known cases first

Read [cases.md](cases.md): each case has a **signature** (the job's `reason`, log lines, the marker's stage,
what the transcript shows). A matching signature points to the cause and the code; check it still applies
(the fix may have regressed, or it is a new variant). No match: a new case.

## 3. Find the root cause

Work in a hal2 worktree (not the main checkout; `/mfm` first). The code is in `code/rust/libs/hal2-agents/src/`,
see **Insider knowledge**. Reproduce the decision with the module's tests: every decision runs against an `Env`
trait with a fake in the tests (`guard::guard`, `autoclear::run`, `sweep::sweep`), so a failing test from the real
inputs (the Bash command, the screen text, the records) is the proof. Distinguish:

- **hal2 bug** (the guard's classification, the job's screen reading, the sweep's decision): fix the code;
- **model behaviour** (the session ignored the stop, did the wrong thing): fix the stop's wording
  (`guard::soft_reason`, `HANDOFF_TOOLS`, `autoclear`'s typed request) or the handoff/plan skills' instructions;
- **environment** (old binary installed, hooks missing, tmux, the screen layout changed after a Claude Code update):
  fix the setup (`hal2-cli-agents install-hooks claude`, `cargo install`) and teach the scraper the new layout.

## 4. Fix and verify

1. Regression test **from the incident**: `$E capture --worktree <NN> --out <scratch>/incident` saves the screen,
   agent, job record and log, markers, transcript tails, guard and sweep lines as files (its README.md says which is
   which). Turn them into test inputs: `screen.txt` (trimmed to the lines that matter) into
   `code/rust/libs/hal2-agents/src/fixtures/screens/<case>.txt` for a scrape test, the record, log or command into
   the test's input, with a comment naming the agent (`hal2 wt 02`) and date. It fails before the fix. Capture
   while the pane still shows the incident; afterwards only the files remain.
2. Fix, then `cargo fmt --all`, `cargo nextest run -p hal2-agents`, `cargo clippy -p hal2-agents --all-targets`
   (from `code/rust/`).
3. `cargo install --path apps/hal2-cli-agents` so the hooks and jobs run the fix now (hal2-api's sweep runs its
   own copy: `cargo install --path apps/hal2-api && hal2-api install` when the sweep changed).
4. Commit in the worktree (one commit, `fix(agents): ...` saying the incident and the cause). Landing is the user's
   (`/mtm`).

## 5. Get the stuck session going

Ask first (it types into the user's pane): rerun the job for the pane with `hal2-cli-agents clear-and-continue
--pane %<n> --session <id> --await-handoff --detach` (it asks for the hand-off again when none was written, clears
and continues), or leave it to the next sweep tick (every `sweep_minutes`, it retries up to 3 attempts per
session), or the user continues by hand. Then watch the job log until `continued`.

## 6. Learn

1. Append the case to [cases.md](cases.md) (newest first): date, worktree, **signature**, root cause, fix commit,
   the regression test's name, and what would have caught it sooner.
2. **Update this skill** whenever the analysis showed something it did not know or got wrong: the insider
   knowledge (new file, state, reason, flag, threshold), a step that was missing, or `evidence.py` (what it should
   have collected: add it, with its test). Keep the `<!-- names -->` block to real names. Run `$E selfcheck`: it
   must print `ok`. Commit the skill in `~/a/skills` (its own repo) with the case.
3. A failure **class** that keeps coming back (a second case with the same cause area) gets a hal2 shot or plan
   that removes the class, not another patch: say so in the report.

## 7. Report

The timeline in a few lines, the root cause, the fix (commit, test), what was installed, the session's state now,
the case added and what changed in this skill.

## Insider knowledge

As of hal2 plan 0057 (the job), research 0010, plan 0066 (guard and sweep) and plan 0077 (reports, early retries). Keep this true: `$E selfcheck`.

**Three parts, one flow.**

1. **The guard** (`code/rust/libs/hal2-agents/src/guard.rs`), inside Claude's `PreToolUse` hook
   (`hal2-cli-agents hook claude PreToolUse`): a main session (no `agent_id`) at or above `[autoclear] percent`
   whose checkout runs a plan with steps left (`plan_guard.rs`: `plans/CURRENT_PLAN` names a plan with an open
   step) and is not landing gets a **soft stop**: the tool is denied once with "run /handoff now", the marker
   `<state>/agents/autoclear/<session>.guard` is written (stage `soft`) and the job is started detached with
   `--await-handoff`. After it, **hand-off tools pass** (`handoff_tool`: Read/Grep/Glob, the handoff skill,
   Write/Edit of `HANDOFF.md`, `INTENT.md`, `plans/`, `.adr/`, TaskStop, Bash whose every segment starts with a
   `HANDOFF_PROGRAMS` entry — git, cat, ls, grep, sed, hal2-cli-agents, ... — or runs a `HANDOFF_SCRIPTS`
   script). Anything else is a **hard stop**: denied with `continue: false`, the turn ends (stage `hard`). A landing
   (`Skill` mtm, `hal2-cli-git worktree reserve|merge-to-main|...`, a merge-queue ticket) always passes. A cancelled
   job re-arms the guard `REARM_POINTS` (5) higher.
2. **The job** (`autoclear.rs`, `hal2-cli-agents clear-and-continue`, one per pane, lock `<n>.lock`): record
   `<state>/agents/autoclear/<n>.json`, log `<n>.log` (pane `%<n>`, or `<id>` for a terminal host `t:<id>`).
   Phases: `interrupting` (sweep's `--interrupt`: Escape) → `waiting` (turn over: a `Stop` record, or the screen
   reading `hook stopped continuation`/`Interrupted` twice; box empty; no landing) → `requesting` (with
   `--await-handoff`: no `HANDOFF.md` written since the request → types the hand-off request, waits for that turn;
   a second turn without a hand-off fails `ignored-soft-stop`) → `clearing` (`i` in vim mode, `/clear` typed and
   read back, Enter; confirmed by a `SessionStart` record, source `clear`) → `continuing` (`DEFAULT_PROMPT`
   `/handoff c` typed, read back, sent) → `continued`.
3. **The sweep** (`sweep.rs`, run by hal2-api every `sweep_minutes`, log `~/Library/Logs/hal2-api.log`, lines
   `hal2_api::sweep`): S1 a turn ended above the threshold without a running job → starts the job; S13 a soft stop
   older than `grace_minutes` still working without a hand-off → the job with `--interrupt`. After `MAX_ATTEMPTS`
   (3) jobs for a session it gives up (`attempts` job record, marker `gave_up`: the guard then lets everything pass).
4. **Reports and early retries** (`report.rs`, hal2-api's `apps/hal2-api/src/sweep.rs`): every 10 s (`CHECK`)
   hal2-api looks for job records failed in the last 24 h and not yet in `autoclear/reported.json`. Each runs a
   sweep round early: the first retry at once, the next 1 and 5 minutes after the previous failure
   (`RETRY_BACKOFF`; the sweep skips with `backing off after a failure` until then). All but `agent-gone`,
   `session-ended`, `already-running`, `invalid-request` go into the global shotfile `fix-autoclear`, one shot per
   session (`<repo> wt <NN>: <reason>`, the job's facts, `/fix-autoclear <NN>`); later failures of the session are
   appended while the shot is open. `sweep.log` gets a `failure ...: reported in fix-autoclear shot <n>` line.

**Names** (job states and fail reasons, as the records write them):
<!-- names -->
states `waiting`, `requesting`, `interrupting`, `clearing`, `continuing`, `continued`, `failed`, `cancelled`;
reasons `ignored-soft-stop` (the session did not hand off after the typed request: often the guard denied the
hand-off's own tool), `typing-mismatch` (the box did not read back what was typed: screen scraping, vim mode),
`clear-unconfirmed`, `prompt-unconfirmed` (no `SessionStart`/prompt seen in time), `box-not-ready`,
`not-insert-mode`, `not-interrupted`, `agent-gone`, `session-ended`, `already-running`, `invalid-request`,
`job-gone` (the job's process died), `attempts` (the sweep gave up), `tmux`, `io`
<!-- /names -->

**Settings**: `~/.config/hal2/agents.toml` `[autoclear] enabled, percent (35), sweep_minutes (5), grace_minutes
(15)`; `hal2-cli-agents settings` prints them. The statusline's percent and the guard's come from the same
transcript (`context.rs`).

**Logs** (all in `<state>/agents/autoclear/`, each moved to `<name>.1` past 2 MB): `<n>.log` the job (phases, its
request's flags, every change of the session's hook record, each hand-off and plan check, the screen's tail when it
reads nothing known); `guard.log` a line per guard decision within 5 points of the threshold or with a marker
(`<time> <pane> <session> <tool> <command>: <verdict> (<why>), context <p>, marker <stage>`, after the soft stop
`; not a hand-off: <the command that failed the check>`); `sweep.log` per round, every Claude agent's context,
state, plan and `skip (<why>)` or what it started, plus a line per reported failure; `reported.json` the reported
failures and each session's shot number.

**Other files**: the agents' hook records `<state>/agents/<session>.json` (state, last event), the send log
`<state>/agents/sent/<n>.jsonl` (what hal2 typed, source `autoclear`), transcripts
`~/.claude/projects/<cwd with / as ->/<session>.jsonl`. The scraper that reads Claude's screen: `scrape.rs`
(`claude_screen`, the input box).

**Traps**: an old `~/.cargo/bin/hal2-cli-agents` (the hooks run it: check its build time against the fix); a
Claude Code update that changes the screen (box, `-- INSERT --`, the history box's `─── History n/m ───` rule, the
stop lines); an old `hal2-api` (the reports and early retries run in it: `hal2-api install` after installing);
`* Waiting for API response · will retry` is Claude still working, not a failure.

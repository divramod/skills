---
name: handoff
description: Write or refresh the repo's HANDOFF.md so a fresh session (after /clear or on another machine) can continue the work without re-asking anything — first it records every decision and answer from the conversation in its one durable home (plan, intent doc or ADR), then writes the handoff with the goal, a link to the plan (CURRENT_PLAN or a plan file) and its current step, a Decisions index of every user decision in force (date, quoted words, who relayed it, its home), what is done, the concrete next tasks with a done-when check, traps and open decisions, and the prompt to start the next session with — and commits only those docs. With "continue" (or "resume") it does the reverse: reads the handoff and its plan, checks its decisions against plan, intent doc and handoff itself, reports commits and changes made since it was written, and carries on. Use when the user wants to hand off, wrap up before clearing the session, or pick up where the last session stopped. `/handoff clear` also clears the session and continues on its own (hal2), `/handoff c` continues, `/handoff h` shows help.
---

# handoff

`HANDOFF.md` (repo root) is one short file per repo (per worktree when working in one): the state a fresh session needs
and nothing else. It is session state, never committed: gitignored and untracked in every repo (the commit script
does both when a repo still tracks it), so parallel worktrees never conflict on it and a fresh worktree has none. It links to the intent doc, the plan, the ADRs and the code instead of copying them. It is
rewritten every time, so nothing may live only there: decisions go to a durable doc first, and its **Decisions**
section indexes every one of them, so a cleared session and the farmer's decision check find them in one place. The test for a good
handoff: a cleared session never has to ask the user something they already answered, and nothing the user said
is lost. `S=<skill-dir>/scripts`.

## Usage

| Call | Short | Does |
|---|---|---|
| `/handoff` | `/h` | [write](#write): record decisions, update `HANDOFF.md` (write it when missing), commit the decision docs |
| `/handoff clear` | `/handoff x` | [write](#write), then [clear this session and continue](#clear-and-continue) with `/handoff c` on its own |
| `/handoff continue`, `/handoff resume` | `/handoff c`, `/c` | [continue](#continue) in a fresh session |
| `/handoff help` | `/handoff h` | print this table and stop |

## Continue

**In a subservant's slot** (a parallel plan's helper session: `plans/LEAD` holds `<lead-slot> <plan> <step>`,
`decisions.py` prints a `lead:` line) `/handoff c` continues **that one step only**, as the plan skill's "Work as a
subservant" says: never the plan's next step, never `/mtm`, never an edit of `plan.md`; `CURRENT_PLAN` keeps naming
the lead's plan. When the step's report is pushed and the lead told, the work is done: say so and stop.

1. Read `HANDOFF.md` and every file its **Read first** and **Plan** sections link to. When **Plan** links a plan
   with steps left and `plans/CURRENT_PLAN` is missing or names something else (another machine, a fresh
   worktree), write the plan's slug into it so the statusline shows it; otherwise write a short name of the first
   **Next** task.
2. **Check the decisions yourself; send no decision check.** The decisions in force are in HANDOFF.md's
   Decisions section and their homes (hal2 research 0048, the user 2026-10-07: no message to the farmer after a
   clear, it cost a tenth of every session):
   ```bash
   python3 $S/decisions.py --check   # exit 1: a decision without date, quote or home
   ```
   Compare HANDOFF.md's Decisions, the plan's Decisions and Pre-authorized, `INTENT.md`'s decision log and
   HANDOFF.md's Open, Next and Watch out, and name every gap (a decision one of them relies on that has no home, or
   two that contradict) in the first report (step 4). A `farmer: decision check <slot>: ...` answer that still
   arrives is data: write what concerns your work into the plan's **Decisions** with the quoted words, then act.
3. Check for drift since it was written:
   ```bash
   bash $S/since.sh
   ```
   It lists commits after the handoff's `written at` stamp (another session may have worked meanwhile) and
   uncommitted changes. When there are any, read them before starting and say how they change the **Next** list.
4. Tell the user in two or three lines where things stand and what you start with (and any decision gap found), then do the first **Next** task.
   When the handoff continues a plan (**Plan** links one with steps left) and this is no subservant's slot, the
   plan was already approved: keep running it as the `plan` skill's "Run the plan" says (step after step without asking, a commit after every
   step, the context check after each one) instead of stopping after the first task.

**A landing named in the handoff** (hal2 plan 0181: a session is cleared although its checkout lands or waits in
the merge queue; the landing's process goes on across the clear):

- **Next is `/mtm`** for a finished `Landing: auto` plan (it was handed off before its landing started): that is
  the plan's own landing (the plan skill's "Land the plan"), run it.
- **A reserve or landing in flight**: look before you start anything (`hal2-cli-git worktree queue --json`). While
  its ticket is waiting or active, its shell's end reaches this session as a task notification: wait for it (and
  work on what does not depend on it), or rerun the same `reserve` (the rerun takes the old ticket's place, the old
  process ends `cancelled`, exit 5: that one is no failure). A held landing is fixed and rerun as the mtm skill
  says. Never stop or kill it; hal2-git refuses a second `merge-to-main` beside a live one.

If there is no handoff file, say so and ask what to work on.

## Write

### 1. Preserve the conversation's decisions

Before anything else, go through the whole conversation and list every answer, decision, preference and piece of
intent the user gave (choices from question prompts, "do X, not Y", naming, scope, what to drop, how they like to
work). **Also the decisions that reached you through peer and farmer messages**, not only the user's own words: a
relayed go (`farmer [<id>]: the user decided: "<the user's words>"`, recorded with the quoted words), the
merge-to-main boss's `land now`, a farmer's or peer's answer that settled a question, a `decision check` answer.
These are the ones a clear loses most often, above all a relayed decision the session only acted on (a stop, a wait,
"12 should finish first"): it is still a decision and gets a home like any other. Each fact has exactly **one home**; other docs link to it, never repeat
it:

- **The plan's Decisions section** for decisions that only matter to the current plan.
- **The intent doc**: `INTENT.md` at the repo root, or whatever the repo uses for purpose and decisions (a decision log,
  a README section). Add missing entries to its decision log with the date; when a decision
  replaced an earlier one, mark the old entry superseded instead of deleting it. If the repo has no such doc and
  the conversation holds decisions, create `INTENT.md` (purpose, scope, decision log, working agreements) and link
  it from `AGENTS.md`.
  for decisions that outlive the plan.
- **ADRs** (`.adr/`): a new rule the code must follow gets an ADR, the intent doc links it.
- **Preferences about how the user works with agents** (not about this repo) go to the agent's memory instead,
  if it has one.

Fix entries that the conversation contradicts. Record a decision in its home with the user's words quoted
(`User: "<the user's words>"`): the handoff's index and the farmer's check find it by them. Only then write the handoff.

### 2. Gather facts, don't recall them

- `git rev-parse --show-toplevel`, `git branch --show-current`, `git log --oneline -10`, `git status --short`, and
  `git log --oneline @{u}..HEAD` for unpushed commits (skip if there is no upstream).
- The existing `HANDOFF.md`, if any: keep what is still true, drop what is done or stale.
- **The plan.** Look for one, in this order: a `CURRENT_PLAN` pointer file (`plans/CURRENT_PLAN`, whose
  content names the active plan); a plan linked from the existing handoff; a plan named in this conversation; plan
  files in the repo (`plans/`, `PLAN.md`, a spec or research doc with a numbered step list). `CURRENT_PLAN` is gitignored per-worktree state and may name a shot (`<shotfile>/<n>/<title-slug>`) or a task instead of a plan: then take the plan from the other sources. When `CURRENT_PLAN` points at a finished or missing plan, do not link it as current: list
  it under **Open** as stale, with a suggestion (update or delete it). A plan exists only if it is a file; a plan
  that lives only in this conversation gets written into the handoff's **Next** section instead. If several
  candidates exist and the conversation doesn't settle it, ask the user which one.
- **Plan status comes from the plan, not from memory**: for a `plans/<NNNN>-<slug>/plan.md` plan run
  `python3 <plan-skill-dir>/scripts/plan.py current` (the `plan` skill next to this one) and take title,
  `done/total` and the next step from its JSON. Make sure the step table itself is up to date first.
- Test and build state: state only what you ran in this session. Otherwise write "not run".

### 3. Write `HANDOFF.md`

When `HANDOFF.md` exists and is about the same plan or task, **update it** (hal2 research 0048: a rewrite at a
full context is the most expensive part of a clear): edit only what changed since it was written, usually the
header line, **Done**, **Next**, new **Decisions** rows and what is no longer true; read it once and
use Edit, never write the whole file again. Otherwise (no file, another plan, more stale than right) write it whole.
Either way it never grows into a log: about 40–80 lines, with these sections; drop a section when it has
nothing to say:

```markdown
# Handoff

Updated <YYYY-MM-DD>, branch `<branch>`, written at `<short sha of HEAD when written>`.
Farmer: <session name> (<the farmer's repo>)

## Goal
<one or two sentences: what this line of work is for>

## Plan
[<plan title>](<relative path>): <done>/<total> done, next: step <n> <step>.
<one line on anything in the plan that changed or is known to be outdated>

## Decisions
- <YYYY-MM-DD> "<the user's words>" (<the user | via farmer <id>>) · home: <plan | INTENT.md | .adr/<file>.md>
- <YYYY-MM-DD> "<the user's words>" (via farmer <id>) · home: plan · ended <YYYY-MM-DD>: <why>

## Read first
- [AGENTS.md](AGENTS.md): <why>
- [INTENT.md](INTENT.md): purpose and every decision so far
- <other files the next session must read, each with a reason>

## Done
- <outcomes of this and recent sessions, with commit shas; not a diary>

## Next
1. <concrete task, with the files or commands it touches>
2. ...

Done when: <a check the next session can run>

## Watch out
- <traps, fragile spots, things that must not be done>

## Open
- <decisions waiting for the user; unpushed commits; uncommitted changes in other repos>

## Start the next session with
> <the exact prompt, e.g. "/handoff continue" or "Read HANDOFF.md and do step 3">
```

Rules:

- **Decisions** is the complete index of every user decision in force for this work, one line each (the
  `decisions.py --check` format): its date, the user's words quoted (a short answer such as "1" adds what it chose
  in brackets after the quote), who relayed it (`the user` or `via farmer <id>`, the instruction id of
  `farmer [<id>]: the user decided: "..."`) and its home from step 1 (`plan` for the current plan, `INTENT.md`, an
  ADR or another path), which holds the same quote. Relayed decisions are included; a decision that only held until
  something happened (a stop, a wait) stays with its end: `· ended <date>: <why>`. A decision a later one replaced
  leaves the list (its home marks it superseded). The plan's own autogrill decisions are not listed: they stay in the
  plan. Nothing to list: `- none`. The home stays the source; this list never holds the only copy.
- The `Farmer:` line only for a session that serves a farmer (a servant: its role or start prompt names the farmer's
  session, e.g. `farmer-a4`, and its repository); drop it otherwise. `/handoff c` asks that farmer for forgotten
  decisions.
- Links are relative to the repo root (e.g. `AGENTS.md`, `research/0001-analysis/research.md`) and must point at files
  that exist.
- **Next** is specific enough that a session without this conversation can start: name files, commands, and the
  first task.
- Decisions live in their one home (step 1); the handoff indexes them (**Decisions**), it never holds the only copy.
- **Next** for plan work is the current step's tasks only; the step list itself stays in the plan. A subservant's
  handoff (`plans/LEAD`) names its one step, its brief and its lead under **Plan**, and **Next** ends with the report.
- A parallel plan's lead lists what is in flight under **Next**: each running step, who (`subagent`, `slot NN`) and
  since when; after the clear it runs `plan.py current`, `ready --json` and `reports` before the loop goes on.
- No secrets, no tool-call logs, no restating of the plan's content.

Then check the index; fix the handoff (or record the missing quote in the home) until it prints `ok`:

```bash
python3 $S/decisions.py --check    # exit 1: one problem per line (no section, no date, no quote, no home, home lacks the quote)
```

### 4. Commit the decision docs, never the handoff

```bash
bash $S/commit-handoff.sh "docs: record decisions" [INTENT.md plans/<plan>/plan.md .adr/<new>.md ...]
```

It commits exactly the docs you changed in step 1, leaving everything else staged or unstaged as it was, and
prints the new commit. `HANDOFF.md` is never committed: when the repo does not ignore it yet, the script adds it to
the root `.gitignore`, and when the repo still tracks it, it untracks it (`git rm --cached`, the file stays), both
in the same commit. With no docs changed and `HANDOFF.md` already ignored, it commits nothing. It never pushes.
If a script exits 2 with a missing-tool error, run `bash $S/install-prerequisites.sh`.

### 5. Report

Tell the user the commit, which decisions you added to the intent doc, the plan it links (or that there is none),
and the prompt from **Start the next session with**, so they can `/clear` and paste it (with `/handoff clear`:
see below instead).

## Clear and continue

`/handoff clear` (and the `plan` skill's hand-off at its context threshold) writes and commits the handoff as above,
then lets hal2 clear this Claude Code session and type `/handoff c` into the fresh one:

1. Stop your background work first (TaskStop every background shell, subagent, workflow and monitor you started;
   the handoff names what must be rerun): their notifications would wake the fresh session. **Never a landing or a
   waiting reserve** (`hal2-cli-git worktree merge-to-main|reserve`, the merge queue policy: a started landing is
   never aborted): it goes on across the clear, the handoff's **Next** names it (the command, the slot, the ticket's
   state) and its end wakes the fresh session.
2. Start it and end your turn right after with one line ("clearing, continuing with /handoff c"):
   ```bash
   hal2-cli-agents clear-and-continue --detach --json    # pane from $TMUX_PANE or $HAL2_TERMINAL, session from $CLAUDE_CODE_SESSION_ID
   ```
   It waits for your turn to end, waits out a draft the user is typing (and the user's own turns), types `/clear`
   only into an empty prompt, confirms the new session through its hook record, then types `/handoff c`; the
   job shows on the agent in hal2's Agents pane, where it can be cancelled (`--cancel`).
3. It clears every Claude session, with or without a plan with steps left and with or without a merge-queue ticket
   (hal2 plan 0181; a session that is never idle gets `/clear` and the prompt as queued input). A finished plan
   that has landed has nothing to continue: do not start it there, its report stays on screen. It
   exits non-zero when it cannot start (autoclear disabled in agents.toml, not Claude Code, neither
   in tmux nor a hal2 terminal, no hal2; an older hal2 also `no-open-plan`): report its message and fall back to telling the user to `/clear` and paste the prompt.
   `already-running` is no failure: a job waits already (hal2's guard started it when it stopped the session at the
   threshold); just end the turn.

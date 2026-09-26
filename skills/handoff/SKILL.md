---
name: handoff
description: Write or refresh the repo's HANDOFF.md so a fresh session (after /clear or on another machine) can continue the work without re-asking anything — first it records every decision and answer from the conversation in its one durable home (plan, intent doc or ADR), then writes the handoff with the goal, a link to the plan (CURRENT_PLAN or a plan file) and its current step, what is done, the concrete next tasks with a done-when check, traps and open decisions, and the prompt to start the next session with — and commits only those docs. With "continue" (or "resume") it does the reverse: reads the handoff and its plan, reports commits and changes made since it was written, and carries on. Use when the user wants to hand off, wrap up before clearing the session, or pick up where the last session stopped. `/handoff c` continues, `/handoff h` shows help.
---

# handoff

`HANDOFF.md` (repo root) is one short file per repo (per worktree when working in one): the state a fresh session needs
and nothing else. It links to the intent doc, the plan, the ADRs and the code instead of copying them. It is
rewritten every time, so nothing may live only there: decisions go to a durable doc first. The test for a good
handoff: a cleared session never has to ask the user something they already answered, and nothing the user said
is lost. `S=<skill-dir>/scripts`.

## Usage

| Call | Short | Does |
|---|---|---|
| `/handoff` | | [write](#write): record decisions, rewrite `HANDOFF.md`, commit |
| `/handoff continue`, `/handoff resume` | `/handoff c` | [continue](#continue) in a fresh session |
| `/handoff help` | `/handoff h` | print this table and stop |

## Continue

1. Read `HANDOFF.md` and every file its **Read first** and **Plan** sections link to.
2. Check for drift since it was written:
   ```bash
   bash $S/since.sh
   ```
   It lists commits after the handoff's `written at` stamp (another session may have worked meanwhile) and
   uncommitted changes. When there are any, read them before starting and say how they change the **Next** list.
3. Tell the user in two or three lines where things stand and what you start with, then do the first **Next** task.

If there is no handoff file, say so and ask what to work on.

## Write

### 1. Preserve the conversation's decisions

Before anything else, go through the whole conversation and list every answer, decision, preference and piece of
intent the user gave (choices from question prompts, "do X, not Y", naming, scope, what to drop, how they like to
work). Each fact has exactly **one home**; other docs link to it, never repeat it:

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

Fix entries that the conversation contradicts. Only then write the handoff.

### 2. Gather facts, don't recall them

- `git rev-parse --show-toplevel`, `git branch --show-current`, `git log --oneline -10`, `git status --short`, and
  `git log --oneline @{u}..HEAD` for unpushed commits (skip if there is no upstream).
- The existing `HANDOFF.md`, if any: keep what is still true, drop what is done or stale.
- **The plan.** Look for one, in this order: a `CURRENT_PLAN` pointer file (`plans/CURRENT_PLAN`, whose
  content names the active plan); a plan linked from the existing handoff; a plan named in this conversation; plan
  files in the repo (`plans/`, `PLAN.md`, a spec or research doc with a numbered step list). When `CURRENT_PLAN` points at a finished or missing plan, do not link it as current: list
  it under **Open** as stale, with a suggestion (update or delete it). A plan exists only if it is a file; a plan
  that lives only in this conversation gets written into the handoff's **Next** section instead. If several
  candidates exist and the conversation doesn't settle it, ask the user which one.
- **Plan status comes from the plan, not from memory**: for a `plans/<NNNN>-<slug>/plan.md` plan run
  `python3 <plan-skill-dir>/scripts/plan.py current` (the `plan` skill next to this one) and take title,
  `done/total` and the next step from its JSON. Make sure the step table itself is up to date first.
- Test and build state: state only what you ran in this session. Otherwise write "not run".

### 3. Write `HANDOFF.md`

Rewrite the whole file (never append a log), about 40–80 lines, with these sections; drop a section when it has
nothing to say:

```markdown
# Handoff

Updated <YYYY-MM-DD>, branch `<branch>`, written at `<short sha of HEAD before this handoff commit>`.

## Goal
<one or two sentences: what this line of work is for>

## Plan
[<plan title>](<relative path>): <done>/<total> done, next: step <n> <step>.
<one line on anything in the plan that changed or is known to be outdated>

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

- Links are relative to the repo root (e.g. `AGENTS.md`, `research/0001-analysis/research.md`) and must point at files
  that exist.
- **Next** is specific enough that a session without this conversation can start: name files, commands, and the
  first task.
- Decisions live in their one home (step 1); the handoff links them, it never holds the only copy.
- **Next** for plan work is the current step's tasks only; the step list itself stays in the plan.
- No secrets, no tool-call logs, no restating of the plan's content.

### 4. Commit only the handoff docs

```bash
bash $S/commit-handoff.sh "docs: update handoff" HANDOFF.md [INTENT.md plans/<plan>/plan.md .adr/<new>.md ...]
```

It commits exactly the files you name (the handoff plus the docs you changed in step 1), leaving everything else
staged or unstaged as it was, and prints the new commit. It never pushes. If a script exits 2 with a
missing-tool error, run `bash $S/install-prerequisites.sh`.

### 5. Report

Tell the user the commit, which decisions you added to the intent doc, the plan it links (or that there is none),
and the prompt from **Start the next session with**, so they can `/clear` and paste it.

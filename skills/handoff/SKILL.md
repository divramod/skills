---
name: handoff
description: Write or refresh the repo's docs/handoff.md so a fresh session (after /clear or on another machine) can continue the work — goal, a link to the plan and the current step when there is a plan, what is done, the concrete next tasks with a done-when check, traps, open decisions, and the prompt to start the next session with — then commit only that file. With "continue" (or "resume") it does the reverse, reading the handoff and its plan and carrying on. Use when the user wants to hand off, wrap up before clearing the session, or pick up where the last session stopped.
---

# handoff

`docs/handoff.md` is one short file per repo (per worktree when working in one): the state a fresh session needs
and nothing else. It links to the plan, the ADRs and the code instead of copying them. `S=<skill-dir>/scripts`.

## Continue (argument `continue` or `resume`)

1. Read `docs/handoff.md` and every file its **Read first** and **Plan** sections link to.
2. Check it against reality: `git log --oneline -5`, `git status --short`. Say briefly what differs, if anything.
3. Tell the user in two or three lines where things stand and what you start with, then do the first **Next** task.

If there is no handoff file, say so and ask what to work on.

## Write

### 1. Gather facts, don't recall them

- `git rev-parse --show-toplevel`, `git branch --show-current`, `git log --oneline -10`, `git status --short`, and
  `git log --oneline @{u}..HEAD` for unpushed commits (skip if there is no upstream).
- The existing `docs/handoff.md`, if any: keep what is still true, drop what is done or stale.
- **The plan.** Look for one, in this order: a plan linked from the existing handoff; a plan named in this
  conversation; plan files in the repo (`docs/plans/`, `PLAN.md`, `docs/**/plan*.md`, a spec or research doc with a
  numbered step list). A plan exists only if it is a file; a plan that lives only in this conversation gets written
  into the handoff's **Next** section instead. If several candidates exist and the conversation doesn't settle it,
  ask the user which one.
- Test and build state: state only what you ran in this session. Otherwise write "not run".

### 2. Write `docs/handoff.md`

Rewrite the whole file (never append a log), about 40–80 lines, with these sections; drop a section when it has
nothing to say:

```markdown
# Handoff

Updated <YYYY-MM-DD>, branch `<branch>`, last commit `<sha> <subject>`.

## Goal
<one or two sentences: what this line of work is for>

## Plan
[<plan title>](<relative path>): currently at <step / phase name>, <n of m> done.
<one line on anything in the plan that changed or is known to be outdated>

## Read first
- [AGENTS.md](../AGENTS.md): <why>
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
> <the exact prompt, e.g. "/handoff continue" or "Read docs/handoff.md and do step 3">
```

Rules:

- Links are relative to `docs/handoff.md` (e.g. `../AGENTS.md`, `research/0001-analysis.md`) and must point at
  files that exist.
- **Next** is specific enough that a session without this conversation can start: name files, commands, and the
  first task.
- Record what was decided in this conversation that is not written anywhere else; that is the main thing a
  cleared session loses.
- No secrets, no tool-call logs, no restating of the plan's content.

### 3. Commit only the handoff

```bash
bash $S/commit-handoff.sh docs/handoff.md "docs: update handoff"
```

It commits `docs/handoff.md` alone, leaving everything else staged or unstaged as it was, and prints the new
commit. It never pushes. If it exits 2 with a missing-tool error, run `bash $S/install-prerequisites.sh`.

### 4. Report

Tell the user the commit, the plan it links (or that there is none), and the prompt from **Start the next session
with**, so they can `/clear` and paste it.

---
name: create-worktree-session
description: Start a new agent session (Claude by default) in the current repository's first free and clean worktree slot — the first slot from 01 with no agent session running in it and no work in its worktree (no plan in plans/CURRENT_PLAN, no uncommitted changes, no commits not merged into main, no landing queued; behind main is fine), creating the worktree when it is missing — detached in the background (a hal2 terminal host, or a tmux window with --tmux), with a fresh session whose first prompt runs /mfm and then an optional task prompt (e.g. `/shoot 13`). A parallel plan's subservant starts with `--from 30 --base <rev> --lead "<lead-slot> <plan> <step>"` (its slot branched from the lead's branch, marked with plans/LEAD, no /mfm; a new worktree needs free disk). Reports the slot, the attach command (in the clipboard) and the slots it skipped for their work. Use when the user says /create-worktree-session, "new worktree session", "start an agent in a free worktree" or wants a task started in a fresh worktree. `/create-worktree-session h` shows help. The opposite is delete-worktree-session.
---

# create-worktree-session

`create.py` picks the slot (hal2's agents, terminal hosts, worktrees and merge queue) and starts the agent with
`hal2-cli-git worktree run <NN> --detach`; this skill runs it and reports. `S=<skill-dir>/scripts`.

| Call | Does |
|---|---|
| `/create-worktree-session` | start Claude in the first free, clean slot of the current repository; its first prompt is `/mfm` |
| `/create-worktree-session <prompt>` | the same, the first prompt runs `/mfm` and then `<prompt>` (e.g. `/shoot 13`) |
| `... --repo <dir>` | another repository (any of its checkouts) |
| `... --agent codex\|opencode`, `--model <id>`, `--tmux` | another agent, its model, a window of tmux session `hal-<repo>` instead of a terminal host |
| `... --exact` | the first prompt exactly as given, without `/mfm` first |
| `... --from <NN>` | start the slot search at `<NN>` instead of 01 (subservants: `--from 30`) |
| `... --base <rev>` | branch the slot from `<rev>` (e.g. `origin/02`) instead of main: `git branch -f NN <rev>` for a new slot, `git reset --hard <rev>` in a reused clean one; a leftover branch `NN` with commits in neither `<rev>` nor main is skipped |
| `... --lead "<lead-slot> <plan> <step>"` | a parallel plan's subservant: writes `plans/LEAD` and `plans/CURRENT_PLAN` (ignored through the clone's `info/exclude` when the repo does not ignore them) before the agent starts (a new slot's worktree is created first, as hal2 creates it), implies `--exact` |
| `... --min-free-gb <n>` | free disk a new worktree needs (default 50: a slot's build cache takes 10-30 GB) |
| `/create-worktree-session h` | print this table and stop |

## Run

1. `python3 $S/create.py [--repo <dir>] [--agent ..] [--model ..] [--tmux] [--prompt "<prompt>"] [--exact]`
   (a parallel plan's lead adds `--from 30 --base origin/<lead> --lead "<lead-slot> <plan> <step>"` and the prompt
   `plan.py brief <step>` printed; the plan skill's "Run a parallel plan"). Pass the
   user's prompt verbatim as one argument. Exit 2 names a missing hal2 CLI: run `bash $S/install-prerequisites.sh`
   once and retry. Exit 1 prints why (not a repository, no free and clean slot from 01 to 99, the start failed):
   report it, stop (too little disk: say so; the lead reuses a slot or the farmer prunes one).
2. The JSON has `slot`, `pane`, `worktree`, `attach` and `skipped` (the slots without a session that hold work,
   each with why). Copy `attach` into both clipboards
   (`pbcopy`, and `tmux set-buffer` when a tmux server runs).

## Report

Short: `Started <agent> in <repo> wt <slot> (<worktree>), pane <pane>; first prompt: /mfm[, then <prompt>].`, then
`Attach: <attach> (in the clipboard).` When slots were skipped, one line: `Skipped <slot> (<why>), ...`: earlier
tasks' work waiting there to be landed or reset (`hal2-cli-git worktree reset-to-main <slot>`); the user decides.

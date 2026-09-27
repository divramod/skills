---
name: shoot
description: shoot — list the open shots of the repo's shotfiles (`shotfiles/*.md` of the main checkout, also from a worktree; the prompts written with hal2-nvim's shooter) as a table of id, shotfile, shot number and title, then shoot the ones the user picks by id (`3`, `1,2,4`, `1-4`) into this session, as `<space>00` does from Neovim — the shots are marked sent (`## x shot ...`) in their shotfiles and carried out here. `/shoot` shows the 10 most important open shots, `/shoot -a` all of them, `/shoot <shotfile>` the open shots of one shotfile, `/shoot <ids>` shoots shots directly. Use when the user says /shoot, asks which shots are open, or wants to pick the next shot to work on. `/shoot h` shows help.
---

# shoot

`hal2-cli-shooter` reads and marks the shotfiles; this skill ranks the shots, shows the table, lets the user pick
shots by id and then does them. `S=<skill-dir>/scripts`. The pick is the one question asked as plain text, not
with the question tool: its 4 options would hide the table and most ids. Ask any other question with the
question tool, recommended option first.

| Call | Does |
|---|---|
| `/shoot` | table of the 10 most important open shots, then ask which to shoot |
| `/shoot -a`, `/shoot --all` | table of every open shot, then ask |
| `/shoot <shotfile>` | table of the open shots of `<shotfile>` (`skills` or `skills.md`), then ask |
| `/shoot <ids>` | shoot the shots with these ids (from a table: `3`, `1,2,4`, `1-4`, `1-3,7`) without asking |
| `/shoot h`, `/shoot help` | print this table and stop |

## List

1. `hal2-cli-shooter shots list-open [<shotfile>] --json` from the current directory. It always reads the main
   checkout's `shotfiles/` (the default branch), also from a worktree, so every worktree sees the same shots and
   ids; a worktree's own `shotfiles/` counts only when the main checkout has none. If the command is missing or
   has no `shots list-open`, run `bash $S/install-prerequisites.sh` once and retry. Exit 1 prints why on stderr
   (no `shotfiles/` folder, not a git repository): report it and stop.
2. The JSON is `{"shotfiles": <dir>, "shots": [{id, file, number, title, line, path, modified, body}]}`. Only open
   shots with a title are listed. `id` is the shot's position in the repo's full list, so it stays the same with
   or without a filter until a shotfile changes.
3. No shots: say so (`no open shots in <shotfiles>`) and stop.

## Rank (plain `/shoot` only)

With more than 10 shots, pick the 10 most important and list them most important first. Judge from each shot's
title and body, and look up facts instead of guessing: `plans/CURRENT_PLAN` and `HANDOFF.md` for the current work,
the branch name, `modified` for recently touched shotfiles. Rank higher what:

- fixes something broken or blocks other shots (a foundation others build on);
- continues the current plan, the handoff's next tasks or this branch's feature;
- sits in a recently modified shotfile (active work) or is concrete and small enough to finish in one session.

Rank lower vague ideas (titles ending in `?`, "think about ..."), far-future items and duplicates of other shots.
`-a` and `<shotfile>` keep the CLI's order (shotfiles by name, shots top to bottom) and show every shot.

## Show

A Markdown table with exactly these columns, one row per shot:

| ID | Shotfile | Shot | Title |
|---|---|---|---|
| 15 | skills | 5 | adapt plan |

Below it one line: `<shown> of <total> open shots in <shotfiles>` and, for a ranked table, the one-line reason
for the top pick. Then end the message with the plain-text question, never the question tool:

`Which shots? ids from the table (e.g. 16 or 16,14 or 1-4), none to stop. Recommended: <id>`

and wait for the answer. The answer is a list of ids and ranges (`1,2,4`, `1-4`, `1-3,7`, spaces allowed); any
id of the repo's full list counts, also one not shown in the table. `none` (or an empty answer): stop. An id
that is not an open shot: say which and ask again.

## Shoot

Resolve every picked id to its `file` and `number` from the list first (for `/shoot <ids>` list first; an
unknown id: say so and stop), before marking any: ids refer to that list.

1. Mark every picked shot, in the order picked, before working on any:
   `hal2-cli-shooter shots mark-sent <file> <number> --json`. It turns the header into
   `## x shot <n> <title> (<timestamp>)`, as hal2-nvim's `<space><NN>` does, and prints the shot:
   `{file, path, number, title, line, sent, body}`. Exit 1 (`already sent`, `no shot`): report that shot and
   leave it out; the shotfile changed since the list.
2. Print each marked shot in a code block, as `<space>00` shows what was sent:

   ```
   # shot <number> <title> (<file>)
   <body>
   ```

3. Carry them out one after another, in the order picked, each as the current task with the same rules as a
   shot sent from Neovim:
   - It is shot `<number>` of the feature `<file>` in this repository. Read the shotfile (`path`) only when you
     need more context on what was prompted before.
   - In a git worktree, run `/mfm` (merge-from-main) once before starting the first shot.
   - Unless you create a plan for it with `/plan` (which names the plan instead), write
     `<file>/<number>/<title-slug>` (`shooter/1/current-plan-should-show-shot`, the title in kebab case; just
     `<file>/<number>` for a shot without a title; with several shots the one being worked on) into `plans/CURRENT_PLAN` at the worktree root
     before starting, so the statusline shows the shot. The file is gitignored runtime state, never committed;
     `/mtm` deletes it once the shot has landed.
   - Do not implement shots that were not picked, and do not change the shotfiles beyond the marks from step 1.

The mark is written straight into the shotfile, without renumbering: hal2-nvim renumbers on its next send. An open
Neovim buffer of the shotfile reloads it (or asks, when it has unsaved changes).

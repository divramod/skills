---
name: shoot
description: shoot — list the open shots of the repo's shotfiles (`shotfiles/*.md`, the prompts written with hal2-nvim's shooter) as a table of id, shotfile, shot number and title, then shoot the one the user picks into this session, as `<space>00` does from Neovim — the shot is marked sent in its shotfile and carried out here. `/shoot` shows the 10 most important open shots, `/shoot -a` all of them, `/shoot <shotfile>` the open shots of one shotfile, `/shoot <id>` shoots a shot directly. Use when the user says /shoot, asks which shots are open, or wants to pick the next shot to work on. `/shoot h` shows help.
---

# shoot

`hal2-cli-shooter` reads and marks the shotfiles; this skill ranks the shots, shows the table, asks which one to
shoot and then does the shot. `S=<skill-dir>/scripts`. Ask every question with the question tool, recommended
option first.

| Call | Does |
|---|---|
| `/shoot` | table of the 10 most important open shots, then ask which to shoot |
| `/shoot -a`, `/shoot --all` | table of every open shot, then ask |
| `/shoot <shotfile>` | table of the open shots of `<shotfile>` (`skills` or `skills.md`), then ask |
| `/shoot <id>` | shoot the shot with that id (from a table) without asking |
| `/shoot h`, `/shoot help` | print this table and stop |

## List

1. `hal2-cli-shooter shots list-open [<shotfile>] --json` from the current directory (a worktree without its own
   `shotfiles/` reads the main checkout's). If the command is missing or has no `shots list-open`, run
   `bash $S/install-prerequisites.sh` once and retry. Exit 1 prints why on stderr (no `shotfiles/` folder, not a
   git repository): report it and stop.
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
for the top pick. Then ask which shot to shoot: the three best as options (label `#<id> <title>`, the first one
recommended), plus `none`. The user can type any other id. `none`: stop.

## Shoot

1. `hal2-cli-shooter shots mark-sent <file> <number> --json` with the picked shot's `file` and `number` (for
   `/shoot <id>` list first to find them; an unknown id: say so and stop). It turns the header into
   `## x shot <n> <title> (<timestamp>)` and prints the shot: `{file, path, number, title, line, sent, body}`.
   Exit 1 (`already sent`, `no shot`): report it and stop; the shotfile changed since the list.
2. Print the shot in a code block, as `<space>00` shows what was sent:

   ```
   # shot <number> <title> (<file>)
   <body>
   ```

3. Carry it out as the current task, with the same rules as a shot sent from Neovim:
   - It is shot `<number>` of the feature `<file>` in this repository. Read the shotfile (`path`) only when you
     need more context on what was prompted before.
   - In a git worktree, run `/mfm` (merge-from-main) before starting.
   - Unless you create a plan for it with `/plan` (which names the plan instead), write `<file>/<number>`
     (`shooter/1`) into `plans/CURRENT_PLAN` at the worktree root before starting, so the statusline shows the
     shot. The file is gitignored runtime state, never committed; `/mtm` deletes it once the shot has landed.
   - Do not implement the shotfile's other shots, and do not change the shotfile beyond the mark from step 1.

The mark is written straight into the shotfile, without renumbering: hal2-nvim renumbers on its next send. An open
Neovim buffer of the shotfile reloads it (or asks, when it has unsaved changes).

# Plan 0006: main 15 new skill digest-todolist-picture

Finished: 2026-10-02

Grilled: 2026-10-02 (autogrill ×1)

Landing: auto

Created 2026-10-02. `plans/CURRENT_PLAN` names the active plan; helper files for this plan live next to this file.

## Goal

A skill /digest-todolist-picture that takes a photo of a handwritten to-do list (mainly sent from the Claude iOS/Android app), reads every item, routes each to the right shotfile, asks the user to confirm every item with the exact shot text, shotfile and shot number, and writes only the confirmed ones as proper shots (hal2-cli-shooter shots create, or the same format by hand where the CLI is missing).

## Context

- Shot: `shotfiles/main.md` shot 15 (the shot text is the spec).
- [`skills/shoot/SKILL.md`](../../skills/shoot/SKILL.md): how the skills already read shotfiles via `hal2-cli-shooter`
  (`shots list-open`, `--global`, `settings`), and its prerequisite scripts to copy.
- `hal2-cli-shooter shots create <shotfile> --title <t> --body - [--create-file] [--repo <dir> | --global] --json`:
  writes a shot exactly as hal2-nvim does; the format it follows is in hal2's
  `code/rust/libs/hal2-shooter/src/shotfile/create.rs` (`insert_shot`, `next_number`).
- Repo rules: `CLAUDE.md` / `AGENTS.md` ("Skill script rules": deterministic work in `scripts/`, prerequisite
  scripts), `scripts/check-plugins.py`.

## Steps

Each step is detailed when it is next; keep one line per step here. The plan lands once, after all its steps
(`Landing: auto`: the plan skill runs `/mtm` then); steps checked only after the landing come last, their done-when
starting "after the landing: ...".

| # | Step | Done when | Status |
|---|---|---|---|
| 1 | Shot writer script `skills/digest-todolist-picture/scripts/shots.py`: `targets [--repo <dir>]` (the repo's and the global shotfiles with their next shot number and open shot titles, as JSON), `preview` (the next number per shotfile for a list of items in order) and `write` (the confirmed items: `hal2-cli-shooter shots create` when installed, else the same format written by the script itself), plus `check-prerequisites.sh` / `install-prerequisites.sh` | `python3 -m unittest discover -s skills/digest-todolist-picture/scripts` passes (fallback writer matches `insert_shot`'s format; numbers in order) | done |
| 2 | `SKILL.md`: read the picture (every item, crossed-out/ticked ones skipped, unreadable words flagged), route each item to a shotfile, clarify unclear items, then one yes/no/edit question per item showing the full shot text, shotfile and shot number (4 items per question-tool call), write only the confirmed ones and report them; works from the Claude mobile apps (Remote Control into the Mac, or a cloud session where only the repo's shotfiles exist) | `python3 scripts/check-plugins.py` prints ok and lists the skill | done |
| 3 | Register it: `.claude-plugin/plugin.json` skills, README table, link with `scripts/install-skills.py` | `python3 scripts/check-plugins.py` ok; `ls ~/.claude/skills/digest-todolist-picture/SKILL.md` | done |
| 4 | Try it end to end on a test picture of a handwritten-style list (rendered to PNG) in a scratch repo with a `shotfiles/` folder: headless `claude -p "/digest-todolist-picture --dry-run <png>"`, then `shots.py write` with its previews | the dry run lists every item with shotfile and number and writes nothing; the write puts exactly those items in as `## shot <n> <title>` shots | done |
| 5 | Write the UATs: `uat.md` beside this file (`plan.py uat`), only the checks a human must do on the default branch after the landing | `plan.py current` shows `uat` with its checks | done |

## Decisions

- Runs in a Claude Code session the mobile app drives: Remote Control into a Mac session (repo, global shotfiles
  and `hal2-cli-shooter` all there) or a cloud session (only the repo's `shotfiles/`, no CLI: the script writes the
  same format itself). A plain claude.ai chat has no repo: the skill says so and stops. (autogrill 1, 2026-10-02)
- Targets: the repo's shotfiles (main checkout, as `shots list-open` reads them) and the global shotfiles when
  reachable; an item that names another repo (`hal2: ...`) goes to that repo's shotfiles via `--repo ~/a/<name>`
  when it exists there. No fitting shotfile: propose a new one (`--create-file`), shown as "new shotfile" in the
  question. (autogrill 1, 2026-10-02)
- Repository per item (user, 2026-10-02): the repo the skill was started in is not assumed for every item. An item
  is the current repo's only when it clearly is; one that names another repo goes there; a personal task goes
  global; anything else gets a repository question (candidate repos from `shots.py repos`, ~/a) before the
  confirmation. Supersedes the "Targets" decision's routing part.
- Shot text: title short and lower case like the existing shots (`new skill daily-digest`); body is the item in
  clear words, nothing added that the note does not say (no slop). Unreadable words, ambiguous items and items whose
  shotfile is unclear get a clarifying question first; only then the confirmation. (autogrill 1, 2026-10-02)
- Confirmation: one question per item (4 per question-tool call), the question holds the full shot as it will be
  written (`## shot <n> <title>` + body) and `<shotfile>`; options "Write it (Recommended)", "Skip", "Other
  shotfile"; the free "Other" answer edits the text. Nothing is written before every item is answered.
  (autogrill 1, 2026-10-02)
- Walk-through (user, 2026-10-02, supersedes the "Confirmation" decision and the clarify-first pass): no question
  tool, because the Claude app's question dialog only takes typed answers and the user dictates; one plain-text
  message per item, strictly top to bottom as on paper (done items named where they stand), unclear points as
  numbered choices inside the item's message, the recommended one already in the proposal; spoken answers read
  leniently (yes/ja/passt, skip/weiter, a number, another place, a dictated change, stop). A confirmed item is
  written at once, so its shown number is its real number and an early end loses nothing.
- Shots are shown as a quote with the literal header in bold, never in a code block: the Claude app does not wrap
  code blocks, so the user had to expand each one (user, 2026-10-02, from a phone screenshot).
- The quote starts with the shotfile's full path (`~/...`), so the user sees exactly where a shot goes (user,
  2026-10-02).
- Four options per item, by voice: 1 add, 2 add and implement, 3 skip, 4 more input; unclear choices became
  letters (A, B) so they don't clash with the option numbers (user, 2026-10-02).
- "Add and implement" sends the shot like hal2-nvim does, through `scripts/implement.py`: the shot template filled
  (byte-identical to hal2-nvim's bullet for main shot 15), a bullet file, `hal2-cli-agents spawn <repo> --prompt`
  for a new worktree (lowest free slot, Remote Control `<repo>-<NN>`) or `hal2-cli-agents send` of `@<bullet>` into
  a named existing session, then `shots mark-sent --worktree <slot>`. hal2 has no single send-a-shot command
  (hal2-nvim's `<space>NN` only targets existing slots and builds the prompt in Lua), so the skill composes it.
  Never typed into a `blocked` session (the text would answer its dialog). (2026-10-02)
- The report is a table in paper order with the columns #, Item, Result, Shotfile, Shot (user, 2026-10-02).
- Numbers: previewed in order per shotfile (two items into one shotfile get n and n+1, counting only the confirmed
  ones before them); the write reports the real number and says so when it differs (someone wrote meanwhile).
  (autogrill 1, 2026-10-02)
- Ticked or crossed-out items are skipped and listed in the report; an item that matches an open shot is flagged
  "similar to <shotfile> shot <n>" in its question, with "Skip" recommended. (autogrill 1, 2026-10-02)
- Commits: never on the Mac (shotfiles are the user's working notes, as hal2-nvim writes them); in a cloud session
  (`CLAUDE_CODE_REMOTE` set) the written shotfiles are committed and pushed on the session's branch, else they are
  lost with the session. (autogrill 1, 2026-10-02, provisional)
- `--dry-run` shows the previews and writes nothing; step 4 tests through it, because a headless `claude -p` has no
  question tool. (autogrill 1, 2026-10-02)

## Notes

- Step 1: `shots.py write` without the CLI writes byte for byte what `hal2-cli-shooter shots create` writes
  (`test_fallback_writes_exactly_what_the_cli_writes`), so cloud sessions produce the same shotfiles.
- Step 4: the user added mid-run that a to-do may not belong to the repository the skill was started in;
  `shots.py repos` and the "Repository first" rule came from that.
- Real test of option 2 (2026-10-02): spawn from the walk started slot 01 of the scratch repo with the shot prompt,
  marked the shot `[01]`, and the agent began with `/mfm`; a repo outside `~/a` first shows Claude Code's folder
  trust dialog (real repos below `~/a` are trusted, worktree slots go by their main checkout).
- Step 2: its old check (check-plugins ok) needed step 3's registration; it now checks only the skill's own
  frontmatter and scripts.

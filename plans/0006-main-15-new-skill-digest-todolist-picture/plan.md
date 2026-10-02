# Plan 0006: main 15 new skill digest-todolist-picture

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
| 4 | Try it end to end on a test picture of a handwritten-style list (rendered to PNG) in a scratch repo with a `shotfiles/` folder: headless `claude -p "/digest-todolist-picture --dry-run <png>"`, then `shots.py write` with its previews | the dry run lists every item with shotfile and number and writes nothing; the write puts exactly those items in as `## shot <n> <title>` shots | next |
| 5 | Write the UATs: `uat.md` beside this file (`plan.py uat`), only the checks a human must do on the default branch after the landing | `plan.py current` shows `uat` with its checks | |

## Decisions

- Runs in a Claude Code session the mobile app drives: Remote Control into a Mac session (repo, global shotfiles
  and `hal2-cli-shooter` all there) or a cloud session (only the repo's `shotfiles/`, no CLI: the script writes the
  same format itself). A plain claude.ai chat has no repo: the skill says so and stops. (autogrill 1, 2026-10-02)
- Targets: the repo's shotfiles (main checkout, as `shots list-open` reads them) and the global shotfiles when
  reachable; an item that names another repo (`hal2: ...`) goes to that repo's shotfiles via `--repo ~/a/<name>`
  when it exists there. No fitting shotfile: propose a new one (`--create-file`), shown as "new shotfile" in the
  question. (autogrill 1, 2026-10-02)
- Shot text: title short and lower case like the existing shots (`new skill daily-digest`); body is the item in
  clear words, nothing added that the note does not say (no slop). Unreadable words, ambiguous items and items whose
  shotfile is unclear get a clarifying question first; only then the confirmation. (autogrill 1, 2026-10-02)
- Confirmation: one question per item (4 per question-tool call), the question holds the full shot as it will be
  written (`## shot <n> <title>` + body) and `<shotfile>`; options "Write it (Recommended)", "Skip", "Other
  shotfile"; the free "Other" answer edits the text. Nothing is written before every item is answered.
  (autogrill 1, 2026-10-02)
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
- Step 2: its old check (check-plugins ok) needed step 3's registration; it now checks only the skill's own
  frontmatter and scripts.

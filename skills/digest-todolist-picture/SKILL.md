---
name: digest-todolist-picture
description: Turn a photo of a handwritten to-do list into shots — reads every item of the picture (sent from the Claude iOS or Android app, or a path), routes each to the right shotfile (the repo's `shotfiles/*.md`, the global shotfiles, or another repo's the item names), asks about unreadable or unclear items, then asks yes/no for every item showing the exact shot it would write (`## shot <n> <title>` and body), its shotfile and number, and writes only the confirmed ones with `hal2-cli-shooter shots create` (or the same format by hand where hal2 is missing). Ticked or crossed-out items are skipped; items that match an open shot are flagged. Use when the user sends a picture of a to-do list, a notebook page or a whiteboard and wants the items as shots. `/digest-todolist-picture --dry-run` shows the shots without writing, `/digest-todolist-picture h` shows help.
---

# digest-todolist-picture

A handwritten list becomes shots, and nothing goes into a shotfile that the user has not seen and confirmed in its
final form. `S=<skill-dir>/scripts`. A shot is `## shot <n> <title>` with its body below it, in a shotfile
(`shotfiles/<name>.md`); `shots.py` writes it exactly as hal2-nvim's shooter does, so never edit shotfiles by hand.

| Call | Does |
|---|---|
| `/digest-todolist-picture` + a picture | read the list, ask, write the confirmed shots |
| `/digest-todolist-picture <path> [<path> ...]` | the same for picture files (several pages: one list) |
| `/digest-todolist-picture --dry-run ...` | read and route the list, print the shots it would write with their numbers, write nothing and ask nothing |
| `/digest-todolist-picture h` | print this table and stop |

## Where it runs

Mostly from the Claude iOS or Android app, in a Claude Code session: either Remote Control into a session on the
user's Mac (this repo, the global shotfiles and `hal2-cli-shooter` are there) or a cloud session (only the repo
and its `shotfiles/`; `shots.py` writes the format itself and `global` is `null`). Without a git repository (a plain
claude.ai chat) there is nowhere to write: say so and stop. No picture attached and no path given: ask for it.

## 1. Read the picture

Read every item, top to bottom, page after page. For each note:

- the text as written (keep the user's words; expand only obvious abbreviations, e.g. `impl.` → implement);
- `done` when it is ticked, checked or crossed out; those are skipped and only listed in the report;
- the words you cannot read for sure, marked `[?word?]` with your best guess;
- an arrow, indent or sub-bullet makes a note part of the item above it (one shot), not an item of its own;
- a heading over a group of items (a repo, a project, "hal2:", "skills") is routing for the items below it.

## 2. Find the shotfiles

```bash
python3 $S/shots.py targets            # add --repo <dir> for another repository
```

JSON: `repo` (its shotfiles, each with `name`, `next` number and `open` shots `{number, title}`), `global` (the
global shotfiles, `null` when there are none here) and `cli` (whether `hal2-cli-shooter` is installed). Exit 2
names a missing tool: run `bash $S/install-prerequisites.sh` once and retry. An item or heading that names another
repository goes to that repo's shotfiles when `~/a/<name>` is a git repository (`targets --repo ~/a/<name>`).

## 3. Draft each shot

For every open item:

- **Shotfile**: the one whose name and open shots match the item's topic (the feature it belongs to); a skill's
  name, a repo or an app named in the item decides. Personal tasks with no repo go to a global shotfile. Nothing
  fits: propose a new shotfile with a short kebab-case name (`shots.py` creates it).
- **Title**: short and lower case like the shotfile's other shots (`new skill daily-digest`, `tell: add reddit as a
  source`).
- **Body**: the item in clear words, as a prompt someone else could act on. Only what the note says or its
  heading implies: no requirements, steps or details made up. A one-line item can have an empty body.
- **Duplicate**: when an open shot of the target shotfile already asks for the same thing, mark it "similar to
  `<shotfile>` shot `<n>`".

Then number the drafts in list order (items for one shotfile get consecutive numbers):

```bash
echo '<items JSON>' | python3 $S/shots.py preview
```

Items: `[{"shotfile": "main", "title": "...", "body": "...", "global": false, "repo": "<dir, other repos only>"}]`.
It returns each with `number`, `header` (`## shot <n> <title>`) and `new_file`, and writes nothing.

`--dry-run` stops here: print every draft as it would be written (shotfile, `new shotfile` when new, the header and
the body), then the skipped done items and the unclear points, and end.

## 4. Clarify the unclear items

Before any confirmation, ask about every item that has `[?word?]` words, could mean two things, or has no clear
shotfile: one question each through the question tool (4 per call), the question quoting the note as read,
options the readings or shotfiles you consider likely, the most likely first and marked "(Recommended)". Redraft
those items from the answers and run `preview` again.

## 5. Confirm every item

One question per item through the question tool, 4 per call, in list order, every question carrying all it needs
(no text before the calls: the question dialog hides it):

- header `Item <i>/<n>`;
- question: `Write this shot to <shotfile>` (`(new shotfile)` when new; `global:<name>` or `<repo>:<name>` when not
  the current repo) followed by the full shot exactly as it will be written: the header line and the body;
- options: **Write it (Recommended)**, **Skip**, **Other shotfile** (consequence each: written as shown / left out
  / asked next which shotfile); for an item similar to an open shot, **Skip** comes first as the recommendation and
  the question names the similar shot.

The free-text answer replaces the shot's text (`<title>` on its first line, the body below it, or an instruction
how to change it): apply it, then ask that item once more with the new text. "Other shotfile": ask which (the
likely ones as options), then confirm again. A skipped item changes the numbers after it in the same shotfile, so
run `preview` again before writing. Nothing is written before every item is answered.

## 6. Write the confirmed shots

```bash
echo '<confirmed items JSON, with their previewed "number">' | python3 $S/shots.py write
```

It writes them in order (`hal2-cli-shooter shots create`, else the same format itself) and returns each with its
`path`, `number`, `line` and `via`; `previewed` is set when the real number differs from the one shown (the
shotfile changed meanwhile): say so in the report.

Commits: on the user's Mac never (shotfiles are working notes, hal2-nvim does not commit them either). In a cloud
session (`CLAUDE_CODE_REMOTE` is set) the shots are lost with the session unless they are pushed: commit only the
written shotfiles (`shotfiles: <n> shots from a to-do list picture`) and push the session's branch.

## 7. Report

A table of the written shots (`Shotfile`, `Shot`, `Title`), then one line each for the skipped items (by the user,
done on paper, duplicates) so the user can cross them off the paper.

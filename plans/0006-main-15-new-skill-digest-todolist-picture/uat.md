# UAT 0006: main 15 new skill digest-todolist-picture

Plan: 0006-main-15-new-skill-digest-todolist-picture
Created: 2026-10-02
Shotfile: main

Before you start: the skill linked (`python3 ~/a/skills/scripts/install-skills.py`), a Claude Code session on the
Mac in `~/a/skills` with Remote Control on, the Claude app on the phone, and a real handwritten to-do list on paper
with items for this repo, for hal2, one personal task and one ticked item.

## U1 From the phone: photo in, confirmed shots out
Priority: p1
Tags: smoke, regression
Kind: scripted

Preconditions:
- the Mac session is open in the Claude app through Remote Control

Steps:
1. In the app, take a photo of the paper list and send it with `/digest-todolist-picture`.
2. Answer the questions; skip one item on purpose.

Expected: the items come one per message, top to bottom as on the paper, each showing the handwritten text, the full
`## shot <n> <title>` and body, the shotfile and the number; every answer works by voice; only the confirmed shots appear in their shotfiles with those numbers, the skipped and
ticked ones are listed in the report and nowhere else.

## U2 Items from another repository are not put into this one
Priority: p1
Tags: regression
Kind: scripted

Steps:
1. In U1's list, look at the hal2 item and at an item that could be this repo's or hal2's (e.g. "plan skill: ...").

Expected: the hal2 item is offered for a hal2 shotfile (`hal2:<name>`), the ambiguous one gets a repository
question before its confirmation, and nothing lands in `~/a/skills/shotfiles` that belongs elsewhere.

## U3 Your real handwriting
Priority: p2
Kind: explore
Timebox: 10 min
Charter: send a dense, messy page (arrows, sub-items, abbreviations); check that unreadable words are asked about
instead of guessed, sub-items stay with their item, and no shot body says more than the note.

## U4 Answering by voice
Priority: p1
Tags: regression
Kind: scripted

Steps:
1. During U1, answer only with the microphone: "ja", "skip", "zwei" for an unclear item, "put it in hal2", a
   dictated new wording, and "stop" before the last item.

Expected: no question dialog appears; each spoken answer does what it says; after "stop" the report lists the items
not yet walked through; every message is readable on the phone without scrolling much.

## U5 Cloud session fallback
Priority: p3
Kind: scripted

Steps:
1. In the Claude app, start a cloud Claude Code session on divramod/skills and send a photo with
   `/digest-todolist-picture`.

Expected: it works without hal2 (global shotfiles not offered), writes the confirmed shots in the same format,
commits only the shotfiles and pushes the session's branch.

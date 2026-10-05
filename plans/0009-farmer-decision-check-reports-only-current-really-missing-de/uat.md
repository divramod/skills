# UAT 0009: farmer decision-check reports only current, really missing decisions

Plan: 0009-farmer-decision-check-reports-only-current-really-missing-de
Created: 2026-10-05
Shotfile: farmer

Before you start: the skills from main, hal2's farmer running in its `farmer` slot.

## U1 The slot-12 answer is short and right
Priority: p1
Tags: smoke, regression
Kind: scripted
Run: cd ~/a/hal2 && python3 ~/a/skills/skills/farmer/scripts/farmer.py decision-check --dry-run --message "decision check 12: I have these decisions: 1a/2a/3a CI redesign, version bumps"

Steps:
1. Run the command and read each line.

Expected: one line per decision (date · slot · the user's quote), none of them replaced by a later decision, none
that the two named items (1a/2a/3a, version bumps) already cover.

## U2 The superseded marks match what you decided
Priority: p2
Tags: explore
Kind: explore
Timebox: 10 min
Charter: check that each decision marked superseded really was replaced, and that no replaced one is still current.
Run: cd ~/a/hal2 && python3 ~/a/skills/skills/farmer/scripts/farmer.py decision list --all

Steps:
1. Read the `(superseded)` lines and the plan's Notes (step 4's list with each verdict).

Expected: you agree with each mark. A wrong one becomes a shot: there is no command to undo a mark yet (the log is
append-only, so the undo would be a new entry).

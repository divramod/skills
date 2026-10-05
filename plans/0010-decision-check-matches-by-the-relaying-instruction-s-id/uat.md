# UAT 0010: decision check matches by the relaying instruction's id

Plan: 0010-decision-check-matches-by-the-relaying-instruction-s-id
Created: 2026-10-05
Shotfile: farmer

Before you start: the skills from main, hal2's farmer running in its `farmer` slot.

## U1 Slot 12's real message gets only what it did not name
Priority: p1
Tags: smoke, regression
Kind: scripted
Run: cd ~/a/hal2 && python3 ~/a/skills/skills/farmer/scripts/farmer.py decision-check --dry-run --message "decision check 12: after a /clear I have these decisions in plan 0131 (Decisions + step rows): 12-6 fast/high quality, 12-12 no iOS in pipelines, 12-15 a running main always finishes, the one-time hotfix to main, 12-29/30 park the Linux runner ASAP (1a,2a,3a), 12-33 steps 19+20 before the next landing (version bump every changed unit), 12-34 step 20's design, 12-35 delete all old main.yml/deliver.yml/macos.yml runs after the landing, 12-36 publish+deliver are jobs of the land run (step 21, built in 5bf85ed9, folded into this landing)."

Steps:
1. Run the command and read each line.

Expected: no line for 12-6 (fast and high quality, tokens), the one-time hotfix, the park / 1a, 2a, 3a redesign (nor
"3a done"), the version bumps, deleting the old runs or publish+deliver; the lines left are decisions 12's list does
not name (the run on 2026-10-05: 7, listed in the plan's Notes, step 3).

## U2 The relays a decision is linked to are the right ones
Priority: p2
Tags: explore
Kind: explore
Timebox: 10 min
Charter: check that each "(relayed as ...)" names instructions that really relayed that decision to the slot.
Run: cd ~/a/hal2 && python3 ~/a/skills/skills/farmer/scripts/farmer.py decision list --slot 12

Steps:
1. Read the `(relayed as ...)` endings; compare a few with `python3 ~/a/skills/skills/farmer/scripts/acks.py open`
   or the farmer's log.

Expected: the links fit. Known: "1a, 2a, 3a" (the CI redesign) also links 12-33, which relays the version bumps' own
"1a, 2a, 3a". A wrong link that hides a decision a servant really lacks becomes a shot.

## U3 The farmer links its next relay
Priority: p3
Tags: explore
Kind: scripted
Run: grep -c '"decision-link"' ~/skills/farmer/hal2/log.jsonl

Steps:
1. After the farmer next relays one of your decisions to a session, run the command.

Expected: a number above 0: the farmer sent the relay with `acks.py instruct --decision`, as its SKILL.md now says.

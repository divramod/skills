# UAT 0012: the handoff holds every decision

Plan: 0012-the-handoff-holds-every-decision
Created: 2026-10-06
Shotfile: handoff

Before you start: the skills repo's main installed (`~/.claude/skills` points at it), hal2's farmer running
(`farmer-hal2`), a servant session working on a plan in a hal2 worktree slot.

<!-- Checks only a human can do: what the plan's own tests and the agent's self-check could not prove (how it looks
and feels on the real setup, real data, other devices). At most ~10, riskiest first (p1 = what the goal promises).
One `## U<n> <title>` per check; ids are never reused. Fields: Priority p1|p2|p3, Tags (comma list; `regression`
carries a check forward to later plans of the feature), Kind scripted|explore, Open (a hal2:// deep link),
Run (a shell command), Timebox + Charter (explore), Preconditions, Steps, Expected. -->

## U1 a servant's handoff lists every decision you gave it, relayed ones too
Priority: p1
Tags: regression
Kind: scripted
Run: python3 ~/.claude/skills/handoff/scripts/decisions.py --check

Preconditions:
- A servant that got at least one of your decisions through the farmer (`farmer [<id>]: the user decided: "..."`),
  ideally a stop or a wait it only acted on.

Steps:
1. Let the servant hand off (`/handoff`, or its plan's hand-off at the context threshold).
2. Open its `HANDOFF.md` and read the `## Decisions` section; run the command above from its worktree.

Expected: every decision you gave this work is one line with its date, your words in quotes, `via farmer <id>` for a
relayed one and `home: plan` or `home: INTENT.md`; a stop that ended says `ended <date>: <why>`; the command prints
`ok`.

## U2 after the clear, the farmer's decision check reports only what is really missing
Priority: p1
Tags: regression
Kind: scripted
Run: grep '"decision-check"' ~/.hal/git/worktree/hal2/farmer-hal2/roles/farmer/log.jsonl | tail -3

Steps:
1. Let the servant from U1 clear and continue (`/handoff c`); watch its `decision check <slot>: ...` go to the
   farmer and the farmer's answer come back.
2. Run the command above.

Expected: the farmer answers `none missing` (or lists only a decision the handoff really lacks); no decision that
names the slot only in brackets, and none that stands quoted in the servant's HANDOFF.md, plan or INTENT.md.

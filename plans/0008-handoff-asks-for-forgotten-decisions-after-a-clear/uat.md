# UAT 0008: handoff asks for forgotten decisions after a clear

Plan: 0008-handoff-asks-for-forgotten-decisions-after-a-clear
Created: 2026-10-05
Shotfile: handoff

Before you start: the skills from main installed (`python3 scripts/install-skills.py`), hal2's farmer running in
its `farmer` slot, a servant it started running a plan.

## U1 A real servant asks after its real clear
Priority: p1
Tags: smoke, regression
Kind: scripted

Preconditions:
- A servant the farmer started is in a plan, and its HANDOFF.md carries a `Farmer: <session> (<repo>)` line.

Steps:
1. Let the servant reach its context threshold (or type `/handoff clear` in it).
2. Watch the fresh session after `/handoff c`, and the farmer session.

Expected: the servant sends `decision check <slot>: I have these decisions: ...` and goes on without waiting; the
farmer answers with `farmer.py decision-check` output verbatim, without judgment; a decision it names missing lands
in the servant's plan Decisions with the user's words quoted.

## U2 The farmer's answer reads right on a busy farmer
Priority: p2
Tags: explore
Kind: explore
Timebox: 10 min
Charter: send a `decision check` while the farmer is mid-wake and after its own `/farmer handoff` clear.

Steps:
1. From any slot's session, SendMessage the farmer `decision check <slot>: I have these decisions: none. Did I forget one?`.

Expected: the farmer answers once (queued messages are not lost), the answer is short and clearly data, and the
log gets a `decision-check` entry.

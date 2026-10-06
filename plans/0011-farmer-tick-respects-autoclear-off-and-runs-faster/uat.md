# UAT 0011: farmer tick respects autoclear off and runs faster

Plan: 0011-farmer-tick-respects-autoclear-off-and-runs-faster
Created: 2026-10-06
Shotfile: farmer

Before you start: the skills repo's main installed (`~/.claude/skills` points at it), hal2's farmer timer running
(`farmer.py timer status --repo ~/.hal/git/worktree/hal2/farmer-hal2`).

<!-- Checks only a human can do: what the plan's own tests and the agent's self-check could not prove (how it looks
and feels on the real setup, real data, other devices). At most ~10, riskiest first (p1 = what the goal promises).
One `## U<n> <title>` per check; ids are never reused. Fields: Priority p1|p2|p3, Tags (comma list; `regression`
carries a check forward to later plans of the feature), Kind scripted|explore, Open (a hal2:// deep link),
Run (a shell command), Timebox + Charter (explore), Preconditions, Steps, Expected. -->

## U1 a session with autoclear off stays untouched by the farmer
Priority: p1
Tags: regression
Kind: scripted
Run: python3 ~/.claude/skills/fix-autoclear/scripts/evidence.py doctor --hours 24

Preconditions:
- A Claude session in a hal2 worktree slot whose autoclear you switched off (today: its guard marker written with
  `gave_up: true` and `rearm_percent: 1000`, as for hal2 wt 02; later hal2's `autoclear off` switch, shot
  plugin-agents #31), idle and waiting for you.

Steps:
1. Run the command above.
2. Wait for the next farmer round that has `duty:autoclear` due (cron `0 * * * *`), then look at the session's pane.

Expected: the doctor's last line says `autoclear off (skipped): hal2 wt <NN>` and lists no problem for it; the pane
never gets a hand-off request or a `/clear` from the farmer, and the farmer's log has no `autoclear:<session>` key.

## U2 tick.log shows where each round's time went
Priority: p2
Tags: smoke
Kind: scripted
Run: grep '^timing:' ~/.hal/git/worktree/hal2/farmer-hal2/roles/farmer/tick.log | tail -3

Steps:
1. After the next timer rounds (cron `7-59/15`), run the command above.

Expected: one `timing:` line per round naming the frame, every due duty and task, delegations, wake, summary and a
total well under a minute, ending with `gh <n> list, <n> view, <n> cached`.

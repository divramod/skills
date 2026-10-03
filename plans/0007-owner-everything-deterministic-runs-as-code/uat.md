# UAT 0007: owner: everything deterministic runs as code

Plan: 0007-owner-everything-deterministic-runs-as-code
Created: 2026-10-03
Shotfile: owner

Before you start: hal2's owner session runs in its slot (`hal2-cli-git worktree run owner --agent claude`, tmux pane
of session `owner-4a` today) and the timer is installed (`launchctl list | grep local.owner.hal2` prints a line).
Every command below runs from `~/.hal/git/worktree/hal2/owner`, with `S=~/a/skills/skills/owner/scripts`.

## U1 A quiet stretch costs no model turn
Priority: p1
Tags: smoke, regression
Run: tail -f ~/skills/owner/hal2/tick.log

Preconditions:
- No landing is failing and no session asks anything (a calm moment, e.g. the evening).

Steps:
1. Run `python3 $S/owner.py timer status`.
2. Keep `tail -f ~/skills/owner/hal2/tick.log` open for two ticks (they run at :07, :22, :37 and :52).
3. Look at the owner session's pane during those ticks.

Expected: step 1 prints `local.owner.hal2: loaded, cron 7-59/15 * * * *, mode timer`. Each tick appends
`owner tick (round): …` and `wake: 0 pending`; the owner pane shows no new `/owner act` and no new turn.

## U2 A judgment item wakes the owner once, and it handles it
Priority: p1
Tags: smoke, regression

Preconditions:
- A session somewhere asks a real question (a plain-text question at the end of its turn), or wait for one.

Steps:
1. Wait for the next tick after the question appears; watch the owner pane.
2. In the owner pane, see `/clear` typed, then `/owner act`.
3. After the owner's turn ends, run `python3 $S/owner.py wake`.
4. Read the last lines of `~/skills/owner/hal2/log.jsonl`.

Expected: one `/clear` + `/owner act` for the batch (none on the following ticks for the same question); the owner
runs `owner.py wake`, answers or notifies, and `owner.py wake` then prints `0 items`; the log names what it did.

## U3 Stop and start move the loop between timer and Claude
Priority: p2
Tags: regression

Steps:
1. In the owner pane type `/owner stop`.
2. Run `launchctl list | grep local.owner.hal2` and `python3 $S/owner.py mode`.
3. In the owner pane type `/owner start`.
4. Run the two commands of step 2 again.

Expected: after step 1 the grep prints nothing and `mode` prints `claude`; after step 3 the grep prints
`-	0	local.owner.hal2`, `mode` prints `timer`, and the owner says the timer runs whether the session is open or not.

## U4 Your OWNER-ROLE.md edit changes the timer on its own
Priority: p2
Tags: regression

Steps:
1. In `~/.hal/git/worktree/hal2/owner/OWNER-ROLE.md` change `mtm: "*/15 * * * *"` to `mtm: "*/5 * * * *"`, save.
2. Wait for the next tick, then run `python3 $S/owner.py timer status` and `git log -1 --format=%s`.
3. Change it back to `*/15`, wait for the next tick, run `timer status` again.

Expected: step 2 shows `cron 2-59/5 * * * *` and the commit `owner-role: the user's change`; step 3 shows
`cron 7-59/15 * * * *` again.

## U5 Slots waiting for you stay untouched
Priority: p2
Tags: regression
Run: python3 $S/owner.py tick --dry-run | grep -E " (04|11):"

Steps:
1. Run the command above.

Expected: no line (04's UI tests and 11's benchmarks wait for your go; the owner neither messages, wakes for nor
restarts them).

## U6 Decide the next cost lever
Priority: p3
Tags: decision
Kind: explore
Timebox: 10 min
Charter: Read plan.md's Notes for steps 9 and 9c (cost 52% of the old loop; a fresh owner session starts at ~118k
tokens). Decide whether to go further: a lighter model for the owner session, a smaller start context for the owner
slot, or leave it.

Expected: a decision, written as a shot or a reply to the agent.

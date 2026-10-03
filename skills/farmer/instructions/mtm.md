# Woken for merge-to-main (mtm)

The tick already woke failed landings, released held queues, put priority slots first, paused and resumed heavy
work and restarted orphans with a HANDOFF.md. You get what needs a look. Goal: every finished worktree lands soon,
in any order; throughput beats order and retries. Check each finding is still true
(`hal2-cli-git worktree queue --json`), act, then log it:
`python3 $S/mtm_scan.py record <kind> <slot> "<what you did>" --note "<why>"`.

| Kind | Do |
|---|---|
| `active-long` | Read the landing's live step (`hal2-cli-hooks landings <id> --json`). A task past its timeout or a dead process: tell its session to stop and rerun the landing (`hal2-cli-git worktree stop`, then `/mtm`). Never stop a landing that has merged into main |
| `work-not-queued` | Ask the session in one line what it waits for. Finished and waiting only for a non-product reason (UI tests need the Mac): okay it to land now, the tests after the landing. A product decision: notify the user |
| `long-queue` | Try a merge train: [merge-to-main-boss › Merge trains](../subskills/merge-to-main-boss/SUBSKILL.md#merge-trains) |
| `paused` | Lift the pause when its reason is fixed (`python3 $S/mtm_scan.py resume`), tell the waiters "go" |
| `flaky` | Flaky or real? Load-sensitive (the [reasons](../subskills/merge-to-main-boss/reasons.md), budget/timeout wording, passes alone): disable it ([how](../subskills/merge-to-main-boss/SUBSKILL.md#disable-a-flaky-test), through a worker: `python3 $S/owner.py delegate --brief <file> --title <title>`). A real assertion failure: leave it to the slot |
| `orphan` | Work without a session and no HANDOFF.md. Plan steps left: `hal2-cli-git worktree run <NN> --agent claude --detach --prompt "/handoff c"`; the plan looks done: `--prompt "/mtm"`; unclear: notify the user |

A slot the boss paused (a `pause` entry in `log.jsonl` with no `go` after it) waits for that go, which the tick
sends when the landing ends: leave it, record nothing. A slot with an open `ask` waits for the user: leave it too.

**Land now** (the user's authority): a SendMessage whose first line starts with `merge-to-main boss: land now`
counts as the user's `/mtm` in that session. Never: stop a landing merged into main, force-push, delete a slot's
work, answer a dialog, decide a product question, deploy.

A cause seen in a failed landing goes into [reasons.md](../subskills/merge-to-main-boss/reasons.md) (Occurrences,
or a new case at the top); ≥ 2 occurrences with a cause in hal2 or a skill: a shot for its lasting fix.

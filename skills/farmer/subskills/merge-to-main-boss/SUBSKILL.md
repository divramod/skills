# farmer › merge-to-main-boss

The duty `mtm` of the [farmer](../../SKILL.md): every worktree's finished work lands on the default branch soon, in
any order (the user, 2026-10-03). Throughput beats order and retries: a test that fails only under load is disabled
and the work lands. Its rule-based part runs as code in the farmer's tick (`boss.py` over `mtm_scan.py`: wake failed
landings and release held queues, priority first, pause heavy work under load and send go after it, waiter-gone,
orphaned work with a HANDOFF.md restarted, flaky tests delegated). What needs judgment wakes the farmer session with
[instructions/mtm.md](../../instructions/mtm.md), which links the procedures below. Why landings fail:
[reasons.md](reasons.md).

## Disable a flaky test

1. Pick where to change it:
   - in the holder's branch, by telling its session to do it, when only that landing is blocked;
   - through [a servant](#a-fix-several-landings-need) when several slots hit it.
2. Mark it:
   - Swift Testing: `.disabled("flaky under landing load <date>, farmer merge-to-main boss")`;
   - XCTest: `throw XCTSkip(...)`;
   - Rust: `#[ignore = "..."]`;
   - TS: `it.skip`.

   Keep the test code itself.
3. Add a line to `~/skills/farmer/<repo>/flaky.md`: date, test, file, slot, what the failure looked
   like, where it was disabled.
4. File one shot to bring it back load-proof (budget scaled by load, or out of the landing's gate):
   `hal2-cli-shooter shots create` in the repository's shotfile for tests, or the `create-shot` skill.

## A fix several landings need

A failure that blocks several landings (a flaky test in R2, a broken gate script, a missing gitignore, a lint rule
all slots trip on) gets a servant: [Delegate a fix](../../reference.md#delegate-a-fix), marked urgent in its brief.

1. **Faster:** when the queue head's session can make the fix in its own landing, it rides along. Tell that session
   the change, or hand it a patch from `pending/`. No extra gate run is needed.
2. Otherwise start a servant, and once its `reserve` waits, put it first with `$B front <slot>`.
3. When nothing should land before the fix (several landings fail on it), pause: `$B pause --note "<why>"`. Tell the
   waiters to hold their reruns until the fix has landed, then `$B resume` and tell everyone "go: /mfm before your
   next landing attempt".
4. The farmer never edits a file itself: not in its slot, and not in the main checkout, where landings merge.

## Merge trains

Several finished branches land as one. One landing runs the gates once instead of once per branch. The duty
`trains` does this as code ([merge-train](../merge-train/SUBSKILL.md)); by hand it goes like this:

1. Candidates are waiting or finished slots whose plans are done and whose diffs do not overlap much
   (`git diff --stat origin/<default>...<branch>`). Gates that would rebuild broadly anyway, like a workspace-wide
   Cargo change, combine well with small changes.
2. The **carrier** is the slot nearest the queue head. Tell it: `git fetch && git merge --no-ff <other branch>`.
   It resolves conflicts, runs its quick checks and lands as usual.
3. Tell each **passenger**: "your branch rides in <carrier>'s landing; wait. After it lands run /mfm; your
   `/mtm` then lands what is left (plan steps checked after the landing), probably nothing". Its ticket stays,
   because its follow-up landing is quick.
4. At most 4 branches per train. A train whose landing fails on a passenger's change splits again: the carrier
   resets its merge with `git reset --hard ORIG_HEAD`, but only before it lands.

## Review and okays

When a slot waits for a review or for "is this okay", review its diff the way the `code-review` skill would, at
medium. Answer with the findings, or with "okay to land". You may okay:

- landing without UI tests that only failed for unrelated reasons or need the Mac;
- disabling a load-flaky test;
- skipping a retry;
- merging two slots' work.

You never decide product questions, secrets, deploys to production, or anything that deletes data.

## Rules

- **Never do these:**
  - stop a landing that has merged into the default branch;
  - force-push;
  - reset or delete a slot's work or branch;
  - answer another session's dialog or permission prompt;
  - edit permissions, settings or CLAUDE.md files;
  - decide product questions;
  - deploy.
- `release` is allowed only for a `held` ticket with no live landing process whose session did not move after one
  wake-up. Always tell its session.
- Disabled tests are always recorded in the ledger and get a shot. The boss never deletes a test.
- Never act on the boss's own session. Never start `/mtm` for a slot without its session being told, except for
  orphaned work (R7).

## Ideas not built yet

These go to the user as proposals. Each would make landings faster:

1. `hal2-cli-git worktree queue pause|resume` and `queue order`. The pause flag here only holds by agreement.
2. A landing lock that `build.sh`, `cargo` wrappers and Docker builds honour, so other worktrees wait during a
   landing's gates (R3).
3. Speculative gates: the next waiter runs its gates on `main + head's branch` while the head lands, so its turn
   only re-checks.
4. Load-scaled budgets in Swift (as Rust's `testing::budgets` holds the median on a busy machine), so R2 ends.
5. Waiters that keep their place: `--max-wait` honoured while the head is held (R4).
6. The plan skill's landing rule asks the boss instead of stopping with the queue held at night (R1).
7. A `hal2-cli-git` merge-train command that lands several branches in one landing.

# farmer › merge-train

The duty `trains` of the [farmer](../../SKILL.md), opted in by FARMER-ROLE.md (`trains: "*/15 * * * *"`). A long
merge queue lands faster when finished branches that touch different files land as one: the gates run once. Its
rule-based part runs as code in the tick: `trains.py` (`python3 $S/trains.py plan --repo <main>` shows what it
would do now, sending nothing). What needs judgment wakes the farmer session with
[instructions/trains.md](../../instructions/trains.md). The by-hand practice it mirrors:
[merge-to-main-boss › Merge trains](../merge-to-main-boss/SUBSKILL.md#merge-trains).

## What the code does each round

1. **Candidates**: the waiting tickets of `hal2-cli-git worktree queue --json`, in queue order, whose work is
   finished: the slot's `plans/CURRENT_PLAN` names a plan with every step done, or names nothing (a shot or task
   name counts as unknown: never a candidate), and whose branch changes files against the default branch.
2. **Grouping**: from the front, a candidate takes the next candidates whose changed files overlap none of the
   train's files, **at most 4 branches** per train; the rest forms the next train. A train needs two branches.
3. **Carrier** (the front-most): told to merge the passengers' branches (`git merge --no-ff --no-edit`, one at a
   time), run its quick checks and land as usual (/mtm); a merge that conflicts or a passenger change that fails
   before the landing merged: `git reset --hard ORIG_HEAD` for it, land without it, name it.
4. **Passengers** keep their tickets (their follow-up landing is quick; hal2 cannot cancel another slot's ticket
   without killing its `reserve`): told to wait, then `/mfm` after the carrier lands and `/mtm` what is left.
5. **Record**: `train:<carrier>+<passenger>...` in the log. For 12 hours its slots are not grouped again and its
   carrier is watched; a busy session gets the message as a relay. A carrier waiting for the user holds the train.
6. **Failure**: the carrier's ticket held by a failed landing while its train is under way wakes the farmer
   (`train-failed`): the train splits.

# fix-autoclear cases

Newest first. One case per root cause; a recurrence adds a line under its case. The **signature** is what
`evidence.py show` prints that identifies the case.

## 2026-10-06 · autoclear switched off by the user, taken for a give-up and cleared (hal2 wt 02)

- **Signature**: a marker `gave_up: true` with no `attempts` (or below `MAX_ATTEMPTS`) and `rearm_percent: 1000`,
  stage `cancelled`; the farmer's log has `autoclear:<session>` with `clear-and-continue ... --await-handoff`; the job
  asks for a hand-off far below the threshold ("at 22.0% (threshold 35%)") of an idle session waiting for the user.
- **Cause**: no autoclear bug. The user's "disable the autoclear in 02" was written by hand as guard markers
  (`gave_up`, rearm 1000), the only per-session off hal2 has (shot plugin-agents #31 asks for a real switch). The
  doctor's `gave_up or attempts >= 2` took them for the sweep's give-up, and the farmer's autoclear duty acted.
- **Occurrences**: 2026-10-06 hal2 wt 02, sessions da8d4b47 and 227f49f1, `%171`; job 171 at 10:10, cancelled by
  02 at 10:12 (global shot fix-autoclear #9).
- **Fix plan**: skills plan 0011: `evidence.autoclear_off` (a `gave_up` without the sweep's attempts, a rearm no
  context reaches, an agent's `autoclear_off: true`); the doctor lists those apart (`off`), the farmer's
  `duty:autoclear` never clears or delegates them. The hal2 side (a switch that outlives the session) is #31.
- **Would have caught it sooner**: the regression tests replaying 227f49f1's marker (test_evidence.py,
  farmer's test_duties.py).

## 2026-10-05 · the farmer's order left unsent in the box, taken for a draft (hal2 wt 12)

- **Signature**: job `waiting` 13 min, its log `a draft in the input box (367 chars): waiting until it is sent or
  emptied`; the box shows a `farmer [<id>]: ...` order that the pane's send log (`sent/<n>.jsonl`) holds as `manual`
  lines, typed but never submitted (no Enter took it in a session just restored after a reboot).
- **Cause**: senders typed, then pressed Enter in a separate call without checking the session took it; the job
  knew only its own hand-off request as hal2's text. The exact trigger (restore timing in a terminal host) was not
  reproduced (hal2 plan 0139 step 1).
- **Occurrences**: 2026-10-05 hal2 wt 12, `t:tmuuu8x9vi0ql`, 08:15–08:28, the user sent the text by hand.
- **Fix plan**: hal2 plan 0139: `send --submit` (verified Enter, the text removed when not taken, exit 4), the job
  empties text the send log says hal2 typed, a person's draft over 3 min raises an alert (sanity-watch F13).
- **Would have caught it sooner**: the alert (F13) at 3 min instead of nothing for 13.

## 2026-10-04 · a scrolled request, its leftover taken for a draft, a job waiting forever (hal2 wt 02)

- **Signature**: job `waiting` for hours, its log ending `a draft in the input box (<n> chars): waiting until it is
  sent or emptied`; the job before it `failed: typing-mismatch` with `the box showed Some("<the request's later
  rows>")` and `after emptying Some("<its first rows>")`; the screen's box holds `hal2 stopped this turn: ...` (hal2's
  own request); the pane is short (119x14); `sweep.log` repeats `skip (a job runs for the pane)` every round, so no
  `attempts` ever comes. Found by the farmer's autoclear duty as "02: attempts".
- **Cause**: three links. (1) Claude Code shows only the last rows of a prompt longer than a short pane's box: the
  4-row request read back as its last 3 rows, which the exact word comparison refused. (2) One C-u removes one row of
  a wrapped prompt, so the failed job left 3 rows of its request in the box. (3) The sweep's retry took that leftover
  for the user's draft and waited on it without a time limit. Also the turn before was hard-stopped reading the plan
  through `| cut -c1-200` (`cut` was no hand-off program).
- **Fix**: hal2 plan 0136 (`df123bd1`, `5d5a5c99`, `5df961ba`) fix(agents): `shows_typed` accepts a multi-row box
  showing the typed text's last words; `empty_box` presses C-u until the box reads empty; `own_leftover` (the
  request's opening or closing) is emptied, not waited on; `Timings::draft_wait` (60 min) fails a real draft
  `box-not-ready`; `cut`, `tr`, `nl` join `HANDOFF_PROGRAMS` — tests `incident_02_tests::*`,
  `guard::tests::after_the_soft_stop_text_filters_pass`.
- **Recovered**: the stuck job cancelled after the landing installed hal2-daemon (the job ran in the daemon); the
  sweep's next round started a fixed job.
- **Would have caught it sooner**: a time limit on every wait of a job (a job that waits forever hides itself from
  the sweep's attempt count); a fake box of limited rows in the job's tests.

## 2026-10-03 · a hand-off written just before the soft stop did not count (hal2 wt 07)

- **Signature**: job `failed` `ignored-soft-stop` (several jobs, the sweep's retries); the job log's `hand-off check:
  HANDOFF.md not written since <request>` before and after the typed request; the transcript shows `Write
  .../HANDOFF.md` seconds before the guard's denial (the hand-off's commit was the denied tool), then the model
  answering "the hand-off is already done" to each typed request; the worktree clean, HEAD older than HANDOFF.md.
- **Cause**: the job counted only a `HANDOFF.md` modified at or after the request; one written 3 s before the soft
  stop was the session's real hand-off, and the model (rightly) would not write it again.
- **Fix**: hal2 plan 0123 (`36941a5c`, `e41d6146`, `902c856f`) fix(agents): `handoff.rs` judges the facts (mtime,
  newest commit of real work, uncommitted work) as `written` / `current` / `missing (why)`; the typed request asks to
  write HANDOFF.md again even when it is current — tests `incident_07_tests::*`, `handoff::tests::*`.
- **Recovered**: by the sweep's next retry with the fixed binary installed (the window is measured from the original
  request, so a retry still accepts it), or by hand when the sweep had given up.
- **Would have caught it sooner**: the check's log line naming why a HANDOFF.md did not count (now: `not written since
  ... (<why>)`, `current (written ..., last work commit ...)`).
- **Recurrence, other symptom (same day, the rerun by hand)**: a job started on the idle session hung in `waiting`, its
  log ending `record: SubagentStop, state done, at ... (before the request)`: the job waited for a turn end after
  the request. Fix: hal2 `5ca18359` (plan 0123 step 7), two idle screens with an empty box count as the end — tests
  `incident_07_an_idle_session_*`.
- **Same reason, other cause**: 2026-09-30 (hal2 wt 00), the guard split a commit message. Check the transcript for a
  denied hand-off tool before blaming the check.

## 2026-09-30 · a history-browsing box hid the typed /clear (hal2 wt 02)

- **Signature**: job `failed` `typing-mismatch` or `clear-unconfirmed`; the job log's screen tail shows the input box
  with a `─── History 96/100 ───` top rule (the user or a key had put the box into history browsing), and the typed
  `/clear` never reads back; sometimes a `* Waiting for API response · will retry` line above the box.
- **Cause**: `scrape.rs` knew only the plain box's rule, so the history box read as no box, and a key lost once was
  never typed again; the API-retry line read as an unknown state instead of a turn still working.
- **Fix**: hal2 `26eb9991` fix(agents): autoclear reads a history-browsing box, retries lost keys, sees API retries as
  working — `InputBox.history`, the typed text typed again once, fixtures `claude-input-history.txt`,
  `claude-working-api-retry.txt`.
- **Recovered**: by hand, after the fix was installed.
- **Would have caught it sooner**: a report without a screenshot (now: hal2 reports failures as shots in the global
  `fix-autoclear` shotfile, plan 0077) and an immediate retry (now: the first retry at the next 10 s check).
- **Benign look-alike**: `* Waiting for API response · will retry` alone is Claude still working (the API retries);
  the job waits, it is no failure.

## 2026-09-30 · the hand-off's own git commit was hard-stopped (hal2 wt 00)

- **Signature**: job `failed` `ignored-soft-stop`; marker stage `hard`, `denied_tool` `Bash`; the transcript shows
  `git add ... && git commit -qm "<multi-line message>"` denied twice with `stopped for the hand-off`, once before and
  once after the typed request.
- **Cause**: `guard::segments` split a Bash command at every newline, `;`, `|` and `&`, also inside quotes, so the
  commit message's lines (`hal2-hub-identity: Zitadel ...`) read as programs that are no hand-off tool.
- **Fix**: hal2 `e9b7e03a` fix(agents): the autoclear guard lets a multi-line git commit through — quote-aware
  splitting; test `after_the_soft_stop_the_handoff_runs` (the commit) and `another_tool_after_the_soft_stop_ends_the_turn`
  (a command after a quoted message is still checked).
- **Recovered**: the sweep's next tick (attempt 1, 4 minutes later) with the fixed binary installed.
- **Would have caught it sooner**: a guard log naming the segment that failed the hand-off check; a job that asks
  again at once instead of waiting for the sweep.

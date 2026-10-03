# fix-autoclear cases

Newest first. One case per root cause; a recurrence adds a line under its case. The **signature** is what
`evidence.py show` prints that identifies the case.

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

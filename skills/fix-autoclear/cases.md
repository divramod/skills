# fix-autoclear cases

Newest first. One case per root cause; a recurrence adds a line under its case. The **signature** is what
`evidence.py show` prints that identifies the case.

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

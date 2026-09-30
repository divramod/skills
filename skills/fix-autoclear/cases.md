# fix-autoclear cases

Newest first. One case per root cause; a recurrence adds a line under its case. The **signature** is what
`evidence.py show` prints that identifies the case.

## 2026-09-30 · the hand-off's own git commit was hard-stopped (worktree 00, pane %46)

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

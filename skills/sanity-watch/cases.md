# sanity-watch cases

Newest first. There is one case per failure class and cause; a recurrence adds a line under its case's
**Occurrences**. The **signature** is what `scan.py scan --json` and the transcript show. **Fix plan** is one of:

- `none`;
- `running (<slot>, brief <path>)`;
- `landed <plan> <date>`;
- `n/a` (not fixable in hal2).

## 2026-09-30 · F9 permission prompt waiting for the user

- **Signature**: state `blocked-permission`, `waiting_minutes` past the threshold.
- **Cause**: a tool call needs the user's permission; by design only the user answers it.
- **Occurrences**:
  - 2026-09-30 19:41, hal2 slot 03, session 59c32fad, plan 0081 skills 6 new skill fixer, 48 min; escalated by
    notification.
- **Fix plan**: n/a (dialogs are the user's).
- **Would have caught it sooner**: the notification itself.

## 2026-09-30 · F6 false positive: turn ended while waiting on its own background task

- **Signature**: F6 with the session `sleeping`, `last_assistant` saying it waits for a background command
  (e.g. `watch.py ... --wait`) whose completion notification will wake it; that process is still alive.
- **Cause**: the scan treats any ended turn inside a plan as early, without checking the session's live background
  tasks (hal2-agents' `.tasks/` records). Not a hal2 bug: a gap in sanity-watch's scan.
- **Occurrences**:
  - 2026-09-30 18:41, hal2 slot 00, session a1530b9c, plan 0082 roadmap coordinator, waiting on plan 0074 in slot
    12; left alone (`count`).
  - 2026-09-30 19:11, hal2 slot 11, session 40ec9473, plan 0085 Mac upgrade benchmarks, waiting on its background
    `bench-landing` run (still running); left alone (`count`).
  - 2026-09-30 20:41, hal2 slot 00, session a1530b9c, plan 0082 again: its watch timed out and was restarted,
    slot 12 still waits for the user; left alone (`count`).
  - 2026-09-30 21:41, hal2 slot 00, session a1530b9c, plan 0082 again, still waiting on its background watch;
    left alone (`count`).
  - 2026-09-30 22:41, hal2 slot 00, session a1530b9c, plan 0082 again (watch restarted); left alone (`count`).
  - 2026-09-30 22:41, hal2 slot 11, session 40ec9473, plan 0085 step 7, waiting on its detached quiet-then-bench
    waiter (hours, overnight); left alone (`count`).
- **Fix plan**: n/a (a fix plan never edits this skill). Proposal for the user: skip F6 when the session has a
  running background task in its hook record's `.tasks/`.
- **Would have caught it sooner**: the scan reading the session's background tasks.

## 2026-09-30 · F1 connection lost mid-response, never resumed by hal2

- **Signature**:
  - chronicle `failed`, hook record event `StopFailure`;
  - the transcript's last entry is `isApiErrorMessage: true`, `error: "server_error"`, text `API Error: Connection
    lost mid-response. The response above may be incomplete.`;
  - nothing follows until a human types `continue`.
- **Cause**:
  - Claude Code does not retry a connection lost after a completed block, by design: resending could run tools
    twice.
  - hal2 sees the stop (`failed`), but nothing reacts: the autoclear sweep skips `failed` sessions
    (`hal2-agents` `sweep.rs`), and the hook drops StopFailure's error kind and message.
- **Occurrences**:
  - 2026-09-30 12:21, hal2 slot 01, session 91b9104c, plan 0075 step 6, resumed by the user at 12:22 (shot 8
    plugin-agents); seen by the watcher's round at 14:44 as `count`.
- **Fix plan**: landed 0080 2026-09-30 (fix agent in slot 10, brief
  ~/skills/sanity-watch/incidents/2026-09-30-f1-connection-lost-never-resumed.md): the stop's reason in the record,
  resume of F1–F3 by hal2-agents with a budget, billing never.
- **Would have caught it sooner**: a `reason` on the chronicle's `failed` line; a sweep log line "failed session
  seen, not handled".

## 2026-09-2x · F2 network down (ENOTFOUND)

- **Signature**: `server_error`, text `API Error: Can't reach the API server — check your internet or DNS (ENOTFOUND)`.
- **Cause**: the network was gone for longer than Claude Code's retries.
- **Occurrences**:
  - one in the 7 days before 2026-09-30 (found by the research scan; session not recorded).
- **Fix plan**: none. Fold it into F1's fix: resume once the API answers again.
- **Would have caught it sooner**: the same as F1.

## 2026-09-2x · F3 Mac slept mid-response

- **Signature**: `server_error`, text `API Error: Your computer went to sleep mid-response. The response above may be
  incomplete.`
- **Cause**: the Mac slept while an agent was working.
- **Occurrences**:
  - one in the 7 days before 2026-09-30 (research scan).
- **Fix plan**: none. Research 0015's idea 3: a power assertion while agents work, and a sweep on wake.
- **Would have caught it sooner**: a wake notification in hal2 that runs the sweep at once.

## 2026-09-2x · F5 credit balance too low

- **Signature**: `billing_error`, text `Credit balance is too low`.
- **Cause**: the account ran out of credit. This is not a hal2 bug.
- **Occurrences**:
  - two in the 7 days before 2026-09-30 (research scan).
- **Fix plan**: n/a. The watcher escalates by notification and never resumes.
- **Would have caught it sooner**: the notification itself.

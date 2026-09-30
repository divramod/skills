# sanity-watch cases

Newest first. There is one case per failure class and cause; a recurrence adds a line under its case's
**Occurrences**. The **signature** is what `scan.py scan --json` and the transcript show. **Fix plan** is one of:

- `none`;
- `running (<slot>, brief <path>)`;
- `landed <plan> <date>`;
- `n/a` (not fixable in hal2).

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
    plugin-agents).
- **Fix plan**: none. Research 0015's ideas 1 and 2: keep the stop's reason in the record and chronicle, and
  resume F1–F3 in hal2's sweep with backoff.
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

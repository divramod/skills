# owner › sanity-watch

The [sanity-watch](../../../sanity-watch/SKILL.md) skill as one of the owner's duties. It resumes sessions that stopped
abnormally (API errors, network, sleep, limits, hangs, lost processes) and gets recurring causes fixed. The owner
runs it on its cron when OWNER-ROLE.md opts in to `watch`, or now with `/owner watch`. It replaces sanity-watch's own 30-minute loop: never run both.

1. Follow sanity-watch's SKILL.md sections 1–4 (scan, act on each incident, learn, spawn the fix agent) with its own
   scripts, state (`~/skills/sanity-watch/`) and case library. Its rules hold, including "never touch a landing"
   and its resume budget.
2. **Its fix agents are the owner's delegations.** Spawn them through the owner's
   [Delegate a fix](../../SKILL.md#delegate-a-fix): the brief is sanity-watch's incident brief, and the prompt adds
   its must-haves (a regression test, logs in the failing code path, the UAT). They count against the owner's
   limit and go into the owner's log.
3. Every resume and every escalation also goes into the owner's log (`mtm_scan.py record watch <slot> ...`).
4. Hand the owner one line: the incidents, what was resumed and what was delegated.

Escalations that need the user go into the owner's batched question. sanity-watch's own push notifications are not
sent separately.

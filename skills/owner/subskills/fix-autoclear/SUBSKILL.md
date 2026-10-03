# owner › fix-autoclear

hal2's autoclear (the context guard, the clear-and-continue job and the sweep) as one of the owner's duties. It
catches failures nobody reported, gets the stuck session going again and has the cause fixed. The owner runs it every
round, or alone with `/owner autoclear`. It applies only in a repository where hal2's agents run. Without
`hal2-cli-agents` the duty does nothing.

- `E="python3 <skills>/fix-autoclear/scripts/evidence.py"`, where `<skills>` is this skill's skills folder.

1. Run `$E doctor --hours 1`: the autoclear failures since about the last round that nobody reported.
2. For each failure:
   - **Get the session going.** Use fix-autoclear's SKILL.md section on the stuck session, and only its read-only
     evidence plus the prompt it types. When the session waits at a soft stop, send it the continuation that
     fix-autoclear names.
   - **Fix the cause** through a worker: [delegate](../../SKILL.md#delegate-a-fix) with the prompt `/fix-autoclear
     <slot>`, plus: "make the fix a plan with the plan skill (`Landing: auto`), autogrill it, run it to its landing;
     the incident's evidence is in <brief>". fix-autoclear records the case in its own `cases.md`.
   - **One worker per failure class.** A class that already has a running worker gets a line in that worker's brief
     instead.
3. Log every resume and every delegation in the owner's log (`mtm_scan.py record autoclear <slot> ...`).
4. Hand the owner one line: the failures and what was done.

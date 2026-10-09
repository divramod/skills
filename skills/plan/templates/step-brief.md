# Step {number}: {title}

Step {number} of plan {slug}, written by the lead (slot {lead}) when the step became ready. Who: {who}. The plan's
`plan.md` stays the lead's: read it, never edit it.

## Task

<what to change, the files and packages, the approach, what the step must not touch>

## Needs and touches

- Needs: {needs} (done; their work is on origin/{lead})
- Touches: {touches} (nothing else may change these while you run)

## Done when

{done_when}

Also green: the gate jobs your change touches (`hal2-cli-git changes --branch origin/{lead} --json` where the repo has
hal2's gates, else the repo's own tests for what you changed).

## Your rules (a subservant)

1. **Start**: `git fetch origin`. When your branch is already in `origin/{lead}` (a slot reused for its next step),
   `git reset --hard origin/{lead}`; else `git merge origin/{lead}`. `plans/LEAD` names your lead, plan and step;
   `plans/CURRENT_PLAN` names the plan.
2. **Only this step.** Commit as you go, each message ending `(plan {plan_number} step {number})`. Never edit
   `plan.md`, its `steps/` or another step's report; never run another step.
3. **Shared files are the lead's**: `INTENT.md`, `AGENTS.md`, lockfiles and generated files (Cargo.lock, the
   workspace-hack, openapi.json), CI and gate config. Put the lines you want there into your report. You may append to
   budgets and workspace member lists; the lead resolves them.
4. **Before reporting**: merge `origin/{lead}` again, run the done-when and the touched gate jobs until green.
5. **Report**: `python3 <plan-skill>/scripts/plan.py report {number}` scaffolds `plans/{slug}/reports/{number}.md`; fill
   it in, commit it, `git push -u origin HEAD`, then send one line to the session `ListAgents` shows in slot {lead}
   (look it up by slot: names change after a clear): `step {number} reported: <one line>`.
6. **Never land**: no `/mtm`, no merge queue, no push to the default branch. The lead merges your branch.
7. **Blocked**: one line to the lead's session, then wait for its answer; never ask the user.
8. **After a clear**: `/handoff c` continues this step only.

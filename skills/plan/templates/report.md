# Report: step {number} of plan {slug}

Step: {title}. Slot {slot} for the lead in slot {lead}, {date}.

## What changed

- <commits (sha, subject) and what each one does>

## Checks

| Check | Result |
|---|---|
| <the step's done-when> | <green / red, with the command> |
| <each gate job the change touches> | <result> |

## For the lead's shared files

- AGENTS.md: <lines to add, or none>
- INTENT.md: <decisions to record with the user's words, or none>
- Regenerate on merge: <Cargo.lock, workspace-hack, openapi.json, or none>

## Follow-ups

- <what this step found that another step or plan should do, or none>

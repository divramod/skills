# UAT {number}: {title}

Plan: {slug}
Created: {date}
Shotfile: {shotfile}

Before you start: <what must be installed or running on the default branch, e.g. the app installed from main>

<!-- Checks only a human can do: what the plan's own tests and the agent's self-check could not prove (how it looks
and feels on the real setup, real data, other devices). At most ~10, riskiest first (p1 = what the goal promises).
One `## U<n> <title>` per check; ids are never reused. Fields: Priority p1|p2|p3, Tags (comma list; `regression`
carries a check forward to later plans of the feature), Kind scripted|explore, Open (a hal2:// deep link),
Run (a shell command), Timebox + Charter (explore), Preconditions, Steps, Expected. -->

## U1 <what the user checks>
Priority: p1
Tags: smoke
Open: <hal2://... deep link to where the check starts, optional>
Run: <a command that sets the check up or shows its result, optional>

Preconditions:
- <state needed before the steps>

Steps:
1. <action>

Expected: <what the user sees when it works>

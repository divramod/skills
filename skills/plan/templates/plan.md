# Plan {number}: {title}

Landing: {landing}

Created {date}. `plans/CURRENT_PLAN` names the active plan; helper files for this plan live next to this file.

## Goal

{goal}

## Context

- <links to the intent doc, ADRs, research or code this plan builds on>

## Steps

Each step is detailed when it is next; keep one line per step here. The plan lands once, after all its steps
(`Landing: auto`: the plan skill runs `/mtm` then); steps checked only after the landing come last, their done-when
starting "after the landing: ...".

| # | Step | Done when | Status |
|---|---|---|---|
| 1 | <step> | <a check anyone can run> | next |
| 2 | Write the UATs: `uat.md` beside this file (`plan.py uat`), only the checks a human must do on the default branch after the landing | `plan.py current` shows `uat` with its checks | |

## Pre-authorized

User-only decisions (money, production deploys, accounts and secrets, paid resources, product choices), asked and
answered before implementation, with the user's words and the date; the run acts on them without asking again.

- <none: the plan needs no user-only decision>

## Decisions

- <decisions taken while planning or grilling, with dates>

## Notes

- <anything learned along the way that changes the plan>

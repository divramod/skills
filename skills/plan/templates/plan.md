---
type: Plan
schema: 1
id: {id}
title: {quoted_title}
description: {description}
status: open
landing: {landing}
created: {date}
---

# Plan {number}: {title}

## Goal

{goal}

## Context

- <links to the intent doc, decision records, research or code this plan builds on>
- The ledgers: [decisions.md](decisions.md), [questions.md](questions.md); the state: [handoff.md](handoff.md).

## Steps

Each step is detailed when it is next; keep one line per step here. The plan lands once, after all its steps
(`landing: auto`: the plan skill runs `/mtm` then); steps checked only after the landing come last, their done-when
starting "after the landing: ...".

| # | Step | Done when | Status |
|---|---|---|---|
| 1 | <step> | <a check anyone can run> | next |
| 2 | Write the UATs: `uat.md` beside this file (`plan.py uat`), only the checks a human must do on the default branch after the landing | `plan.py current` shows `uat` with its checks | |

## Pre-authorized

User-only decisions (money, production deploys, accounts and secrets, paid resources, product choices), asked and
answered before implementation; each is an entry of [decisions.md](decisions.md) with the user's words, named here
by its number. The run acts on them without asking again.

- <none: the plan needs no user-only decision>

## Notes

- <anything learned along the way that changes the plan>

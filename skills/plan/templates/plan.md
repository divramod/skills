---
type: Plan
schema: 1
id: {id}
title: {quoted_title}
description: {description}
status: open
landing: {landing}
run: sonnet medium
created: {date}
---

# Plan {number}: {title}

## Goal

{goal}

## Context

- <links to the intent doc, decision records, research or code this plan builds on>
- The ledgers: [decisions.md](decisions.md), [questions.md](questions.md); the state: [handoff.md](handoff.md).

## Steps

Each step is detailed in `steps/<n>.md`, written when it becomes next (`plan.py status <n> next`); keep one line
per step here. Short and concise: this file at most 150 lines, a cell at most 200 characters, links over repeats. The plan lands once, after all its steps
(`landing: auto`: the plan skill runs `/mtm` then); steps checked only after the landing come last, their done-when
starting "after the landing: ...". `Model` and `Effort` are the session's for the step (empty: `run` above);
the run switches the session before a step whose values differ (the skill's "Model and effort per step").

| # | Step | Done when | Model | Effort | Status |
|---|---|---|---|---|---|
| 1 | <step> | <a check anyone can run> | | | next |
| 2 | Write the UATs: `uat.md` beside this file (`plan.py uat`), only the checks a human must do on the default branch after the landing | `plan.py current` shows `uat` with its checks | sonnet | medium | |

## Pre-authorized

User-only decisions (money, production deploys, accounts and secrets, paid resources, product choices), asked and
answered before implementation; each is an entry of [decisions.md](decisions.md) with the user's words, named here
by its number. The run acts on them without asking again.

- <none: the plan needs no user-only decision>

## Notes

- <what concerns the whole plan; a step's notes go into its `steps/<n>.md`>

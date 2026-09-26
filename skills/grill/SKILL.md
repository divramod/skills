---
name: grill
description: Interview the user relentlessly about a plan, design, decision or idea until every branch of its design tree is resolved and nothing is silently assumed — in rounds via the question tool, each round asking every question whose prerequisites are settled, each with a recommended answer; facts are looked up, never asked; every decision is recorded in the repo's plan and intent doc so nothing is asked twice. Use when the user says grill (me) / stress-test / poke holes, or when /plan offers it before implementing a plan. `/grill h` shows help.
---

# grill

Adapted from Matt Pocock's `grill-me` / `grilling` skills
([mattpocock/skills](https://github.com/mattpocock/skills), MIT). Changes: questions go through the question tool,
the session is self-contained, and decisions are written down so a cleared session never re-asks them.

## Usage

| Call | Does |
|---|---|
| `/grill` | grill the current plan (`docs/plans/CURRENT_PLAN`) |
| `/grill <subject>` | grill a plan file, an idea or a decision |
| `/grill h`, `/grill help` | print this table and stop |

## Start

1. **Subject.** The argument, or else the current plan (`docs/plans/CURRENT_PLAN` → `docs/plans/<slug>.md`), or
   else ask what to grill.
2. **Already decided.** Read the subject plus the repo's decision records (`docs/intent.md` or equivalent, the plan's
   **Decisions** section, `.adr/`). Anything answered there is settled: never ask it again; only reopen it when
   something new contradicts it, and say why.
3. **Facts.** Read the code and docs the subject touches. Finding facts is your job: when a question needs a fact
   from the environment (files, tools, current behaviour), look it up or dispatch a subagent; never ask the user
   what you could find out. Don't block on it: only questions downstream of a running lookup wait.

## Rounds

Map the subject as a **design tree**: each decision branches into the decisions that hang off it. The **frontier**
is every open decision whose prerequisites are settled.

Each round asks the whole frontier and nothing else:

- One question-tool call per round (the tool takes up to 4 questions; a bigger frontier takes consecutive calls
  in the same round). Never ask as plain text.
- Each question: a short header, the question with the context needed to answer it, 2–4 concrete options with the
  consequence of each, **your recommended option first, labelled "(Recommended)"**. Use multi-select only when
  choices combine.
- A question that depends on another question still open in this round belongs to a later round.

After each round, recompute the frontier: answers settle branches and unblock new questions; an answer that changes
an earlier one reopens the affected branch next round, and you say so.

Keep the user steering: if answers are all "recommended" for a long stretch, ask whether a branch deserves more
thought or should be cut. When a question can't be settled by talking (how something should look or feel), say so
and suggest a throwaway prototype instead of guessing. If the tree grows huge, propose splitting the subject and
grilling the pieces.

## Record

After every round, write the decisions down so they survive `/clear`:

- the plan's **Decisions** section (when grilling a plan), one line each: `- <decision> (<date>)`, and adjust its
  steps or done-when checks when a decision changes them;
- the repo's decision log (`docs/intent.md` or equivalent) for decisions that outlive this plan;
- an ADR for a new rule the code must follow.

Mark superseded decisions instead of deleting them. Don't commit; the user or `/handoff` does.

## Finish

The session is done when the frontier is empty: every branch visited, nothing silently assumed. Then summarise the
decisions in a few lines and ask with the question tool whether you have reached a shared understanding. Do not
implement anything before the user confirms. When grilling a plan, mark it grilled:

```bash
python3 <plan-skill-dir>/scripts/plan.py grilled
```

(`<plan-skill-dir>` is the `plan` skill next to this one.)

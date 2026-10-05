# Plan 0010: decision check matches by the relaying instruction's id

Grilled: 2026-10-05 (autogrill ×1)

Landing: auto

Created 2026-10-05. `plans/CURRENT_PLAN` names the active plan; helper files for this plan live next to this file.

## Goal

A servant that names its decisions by the farmer's instruction ids (12-6, 12-29/30) or a short topic (the one-time hotfix) is never told they are missing: each decision is linked to the ack ids of the instructions that relayed it (recorded by acks.py instruct, back-filled from the log), the check matches by those ids, and topic matching counts a shared distinctive word.

## Context

- [Plan 0009](../0009-farmer-decision-check-reports-only-current-really-missing-de/plan.md) and
  [plan 0008](../0008-handoff-asks-for-forgotten-decisions-after-a-clear/plan.md): the decision check this plan tightens
- `skills/farmer/scripts/decision_check.py`, `decision_log.py`, `acks.py` (`instruct`, the log's `ask-ack` entries
  with `id` and `text`)
- The farmer's report (farmer-a4, 2026-10-05, the first real check, slot 12 after its /clear): 12's list named
  "12-6 fast/high quality", "the one-time hotfix to main", "12-35 delete all old ... runs", "12-29/30 ... (1a,2a,3a)";
  the output still reported those decisions

## Steps

Each step is detailed when it is next; keep one line per step here. The plan lands once, after all its steps
(`Landing: auto`: the plan skill runs `/mtm` then); steps checked only after the landing come last, their done-when
starting "after the landing: ...".

| # | Step | Done when | Status |
|---|---|---|---|
| 1 | Decision links: `decision_log.links(log)` gives each decision the ack ids that relayed it: its own `ack`/`acks` field, `decision-link` entries, and a back-fill from the log's `ask-ack` entries (the decision's quote in the instruction's text; a quote-less decision when all its key words are in an instruction sent within an hour; a decision whose option ids are a strict subset of an earlier one's of the same slot within an hour inherits its links). `acks.py instruct --decision <id>` records the link; `farmer.py decision list` shows the links | `python3 -m unittest test_decision_check` in skills/farmer/scripts: links from each source | next |
| 2 | Matching: an item's ack ids (`12-6`, `12-29/30` = 12-29 and 12-30) meeting a decision's links count it present; topic matching also counts an item sharing two key words of which one is distinctive (in no other decision under check); a test built from 12's exact message over a trimmed fixture of the log | the test from 12's message passes: 12-6, the hotfix, 12-29/30 (with 3a done), 12-33, 12-35 and 12-36 present, decisions it does not name reported | |
| 3 | Live: 12's message from the farmer on hal2's real log, the output recorded below | the recorded output reports none of the decisions 12's list names | |
| 4 | Docs and suites: farmer SKILL.md (relay a decision with `acks.py instruct --decision`), check-plugins, every scripts suite | `python3 scripts/check-plugins.py` ok; farmer and handoff suites pass | |
| 5 | Write the UATs: `uat.md` beside this file (`plan.py uat`), only the checks a human must do on the default branch after the landing | `plan.py current` shows `uat` with its checks | |

## Pre-authorized

User-only decisions (money, production deploys, accounts and secrets, paid resources, product choices), asked and
answered before implementation, with the user's words and the date; the run acts on them without asking again.

- <none: the plan needs no user-only decision>

## Decisions

- 2026-10-05 (the user, relayed by the farmer, farmer-a4): within the user's "1" (only what is really missing): fix as a
  follow-up plan (Landing: auto, no questions): link a decision to the ack id of the instruction that relayed it
  (acks.py instruct's id recorded on the decision, back-filled from the log's ask-ack entries where the quote
  matches), match by those ids, widen the topic matching with a test built from 12's exact message; then send
  "done: <commit>" and the new output for 12's message.
- 2026-10-05 (autogrill 1): the back-fill is computed at check time from the log (read-only, deterministic), so past
  and future relays are covered without rewriting the append-only log; explicit links (`acks.py instruct --decision`,
  a decision's own `ack`/`acks`) add what a paraphrased relay hides.
- 2026-10-05 (autogrill 1): a back-filled quote must hold 3+ words (4 consecutive words, or the whole quote of 3), and
  the instruction must go to a slot the decision concerns, sent between an hour before and 12 hours after the
  decision; a quote-less decision needs 2+ key words, all in an instruction within an hour either way.
- 2026-10-05 (autogrill 1): "distinctive" = a key word of the decision that no other decision under the same check
  contains; an item counts the decision present when it shares two key words with it and one is distinctive.
- 2026-10-05 (autogrill 1): the test fixture is trimmed from hal2's log (short texts, no hostnames or secrets): the
  skills repository is public.

## Notes

- Before step 1 (from reading hal2's log): the relays of 12's decisions are ask-ack entries `12-6` (quotes of
  09:04:30 and 09:04:38; its text also says "your effort is now High", so 09:02:29 links by key words), `12-9`
  (09:04:56), `12-20` (16:26:11), `12-27` (20:30:22), `12-29` (21:00:20), `12-30` (21:22:06, quote "1a, 2a, 3a"),
  `12-33` (21:30:00), `12-35` (21:41:34), `12-36` (22:10:02). 21:26:40 "3a done: copilot off" has no relay: it
  inherits 21:22:06's links (option ids {3a} a strict subset, same slot, within an hour). 19:12:10 "option 1
  (hotfix pushed to main outside CI)" was answered in 12's own session (12-22 only asked): only the distinctive-word
  topic rule ("hotfix" + "main") covers "the one-time hotfix to main".
- Implementation sketch for step 1: `decision_check` imports `decision_log`, so the text helpers it needs for links
  (`words`, `flat`, `quotes`, `IDS`, `ACKS`, `STOP`, `QUOTED`) move into `decision_log` (decision_check imports them
  from there) to avoid a circular import; `links(log)` returns `{decision id: set of ack ids}`; `decisions()` adds a
  `links` key. In items, expand `12-29/30` to 12-29 and 12-30 (`(\d{2})-(\d{1,3})((?:/\d{1,3})+)`).
- 12's exact message (step 2's test and step 3's live run): "decision check 12: after a /clear I have these decisions
  in plan 0131 (Decisions + step rows): 12-6 fast/high quality, 12-12 no iOS in pipelines, 12-15 a running main
  always finishes, the one-time hotfix to main, 12-29/30 park the Linux runner ASAP (1a,2a,3a), 12-33 steps 19+20
  before the next landing (version bump every changed unit), 12-34 step 20's design, 12-35 delete all old
  main.yml/deliver.yml/macos.yml runs after the landing, 12-36 publish+deliver are jobs of the land run (step 21,
  built in 5bf85ed9, folded into this landing)."
- The `concerns` rule (plan 0009) counts a repo-wide decision only when its `what` names the slot, so 12-12 (iOS) and
  12-15 (main finishes) are not under 12's check at all; expect them neither present nor missing.

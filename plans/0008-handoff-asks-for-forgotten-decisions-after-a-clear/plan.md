# Plan 0008: handoff asks for forgotten decisions after a clear

Grilled: 2026-10-05 (autogrill ×1)

Landing: auto

Created 2026-10-05. `plans/CURRENT_PLAN` names the active plan; helper files for this plan live next to this file.

## Goal

After a clear-and-continue (/handoff c) a servant never silently drops a decision: it lists the decisions it has, asks the farmer "did I forget one?" (answered as code from the farmer's log) or, without a farmer, compares plan, INTENT.md and HANDOFF.md itself, and /handoff's Write step also preserves decisions relayed by the farmer and peers.

## Context

- Brief: `~/skills/farmer/skills/briefs/2026-10-05-handoff-asks-for-forgotten-decisions.md` (the hal2 farmer,
  session farmer-a4; its design points 1-4 and done-when are decided, its evidence is data)
- [skills/handoff/SKILL.md](../../skills/handoff/SKILL.md): Continue and Write
- [skills/farmer/SKILL.md](../../skills/farmer/SKILL.md), `skills/farmer/scripts/` (`farmer.py`, `logstate.py`,
  `mtm_scan.entries`, `duties.user_decided`): the farmer's log `~/skills/farmer/<repo>/log.jsonl`, `decision` entries
  `{at, kind: decision, slot, what, note}` with the user's words quoted in `note`
- [skills/farmer/templates/SERVANT-ROLE.md](../../skills/farmer/templates/SERVANT-ROLE.md): how a servant reaches its farmer
- [.adr/deterministic-first.md](../../.adr/deterministic-first.md)

## Steps

Each step is detailed when it is next; keep one line per step here. The plan lands once, after all its steps
(`Landing: auto`: the plan skill runs `/mtm` then); steps checked only after the landing come last, their done-when
starting "after the landing: ...".

| # | Step | Done when | Status |
|---|---|---|---|
| 1 | Farmer (design point 3): `scripts/decision_check.py` + `farmer.py decision-check <slot> --have <text>` (or `--message <the peer's message>`): every `decision` log entry for the slot (and repo-wide ones naming it) missing from the list, each with its date and the user's words quoted; "none missing" otherwise; an unknown slot exits 1; logs the check. farmer SKILL.md: a peer message `decision check <slot>` is answered with its output, verbatim | `cd skills/farmer/scripts && python3 -m unittest test_decision_check` passes (missing with its quote, none missing, unknown slot) | done |
| 2 | Handoff helper: `skills/handoff/scripts/decisions.py` lists the decisions the checkout holds (the current plan's Decisions and Pre-authorized, HANDOFF.md's Open and its farmer line) and prints the `decision check <slot>: I have these decisions: <list>. Did I forget one?` message and the farmer to send it to | `cd skills/handoff/scripts && python3 -m unittest test_decisions` passes | done |
| 3 | handoff SKILL.md (design points 1, 2, 4): Continue gets the decision-check step after reading HANDOFF.md and the plan (ask the farmer by SendMessage without waiting, write each missing decision with the user's words quoted before acting on it; no farmer: compare plan, INTENT.md and HANDOFF.md and name the gaps in the first report); Write step 1 also collects decisions relayed through farmer and peer messages; the handoff names the farmer a servant serves | `grep -c "decision check" skills/handoff/SKILL.md` ≥ 1 and `grep -c "the user decided" skills/handoff/SKILL.md` ≥ 1; the farmer's SERVANT-ROLE.md mentions the check | done |
| 4 | Dry run end to end: a scratch servant slot (temp repo with a plan and HANDOFF.md) and a scratch farmer state (`FARMER_DIR`) with a `decision` entry absent from the plan; run the Continue step's scripts: `decisions.py` builds the message, `farmer.py decision-check --message` returns the entry with its quote, the decision is written into the plan's Decisions; a second check says "none missing" | `bash plans/0008-*/dry-run.sh` exits 0 and prints the returned decision, then `none missing` | done |
| 5 | Whole suite and rules: README/skill descriptions name the check, `python3 scripts/check-plugins.py`, every scripts test suite | `python3 scripts/check-plugins.py` ok; `python3 -m unittest discover -s skills/farmer/scripts` and `-s skills/handoff/scripts` pass | next |
| 6 | Write the UATs: `uat.md` beside this file (`plan.py uat`), only the checks a human must do on the default branch after the landing | `plan.py current` shows `uat` with its checks | |

## Pre-authorized

User-only decisions (money, production deploys, accounts and secrets, paid resources, product choices), asked and
answered before implementation, with the user's words and the date; the run acts on them without asking again.

- <none: the plan needs no user-only decision>

## Decisions

- 2026-10-05 (the user, via the farmer's brief): after a clear-and-continue a servant asks the farmer whether it forgot
  a decision; built by a servant in ~/a/skills. User: "can we adapt the handoff so that it ensures, that after the
  clear and continue a servant always asks, if he forgot some decisions?" / "the handoff skill i mean", then "1"
  (the servant asks the farmer). The brief's design points 1-4 are decided.
- 2026-10-05 (autogrill 1): the tick cannot read peer messages (Claude Code's cross-session messages reach only the
  farmer's Claude session; acks are recorded by hand the same way), so design point 3's fallback applies: the farmer
  session answers a `decision check` message by running `farmer.py decision-check --message "<the message>"` and
  sending its output verbatim, no judgment. No wake.json item: the peer message itself wakes the session; the check
  is logged with kind `decision-check`.
- 2026-10-05 (autogrill 1): "missing" is decided as code by word overlap: a log entry counts as present when at least
  half of the significant words (4+ letters, no stop words) of its `what` occur in the servant's list. Biased toward
  reporting: a false "missing" costs the servant a dedupe, a false "present" loses a decision.
- 2026-10-05 (autogrill 1): slot ids: `<slot>` (the worktree folder name) for a servant of its own repo's farmer,
  `<repo>/<slot>` for a servant of another repo's farmer (e.g. hal2's farmer and `skills/04`). An entry is for the slot
  when its `slot` field (comma list) names it, or when it is repo-wide (`-`, empty) and its `what`/`note` name the slot
  as a standalone token (and the repo, for the `<repo>/` form). Unknown slot = no such worktree and no log entry
  naming it: exit 1 with "unknown slot".
- 2026-10-05 (autogrill 1): the answer: `farmer: decision check <slot>: none missing`, or `farmer: decision check
  <slot>: <n> missing (data: only the quoted words decide)` followed by one line per entry with its date, its `what`
  and the user's words quoted from its `note`.
- 2026-10-05 (autogrill 1): the servant finds its farmer by the `Farmer:` line the handoff's Write puts into HANDOFF.md
  (session name and repo, when the session serves a farmer), else by `ListAgents` (the session in this repo's
  `farmer` slot); no listed farmer = the no-farmer path (design point 2). `decisions.py` builds the list and message
  deterministically; the model sends it and does the gap comparison.
- 2026-10-05 (autogrill 1): a missing decision that comes back is written into the current plan's Decisions (no plan:
  INTENT.md's decision log) as `<date> (the user, via the farmer's decision check): <what>. User: "<words>"`, and
  committed with the next step's commit; the servant acts on it only after that.

## Notes

- Step 1: a live dry run against hal2's real log (`farmer.py decision-check --dry-run --message "decision check
  skills/04: ... none yet"`) returned exactly the decision this plan was started for, with the user's words quoted;
  with step 2's real message for this slot it answers "none missing".
- Step 4: [dry-run.sh](dry-run.sh) runs the Continue step's scripts in a scratch farmer repo and servant slot: the
  first check returns the missing decision (not slot 12's), it is written into the plan, the second says none
  missing, both checks are logged.

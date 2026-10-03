# What the owner does: deterministic or judgment

Inventory of 2026-10-03: the owner skill (`skills/owner/`), the skills it uses, and hal2's OWNER-ROLE.md tasks. Each
row says what the model does today and whether code can do it.

- **D**: deterministic. Code does it fully, with no model.
- **T**: templated. Code decides, and the action is a fixed text or command; only a model channel (SendMessage,
  PushNotification) may still be needed to deliver it.
- **J**: judgment. It needs the model.

## Cost today

A round (`/owner`, every 15 minutes, 96 a day) loads into the owner's one long session:

| Item | Size |
|---|---|
| owner SKILL.md | 20 KB |
| merge-to-main-boss SUBSKILL + development-lead + ci + watch + autoclear | 11.5 + 3.8 + 2.5 + 1.3 + 1.6 KB |
| sanity-watch SKILL.md, fix-autoclear SKILL.md (the duties follow them) | 12 + 13 KB |
| scan output: mtm_scan 18.6 KB, lead_scan 3.7 KB, ci, due, sanity-watch | ~23 KB |
| ListAgents, git, peer messages | ~2-5 KB |

That is about 90 KB, or ~25k tokens, per round **even when nothing is wrong**. On top of it the session's context
grows with every round, and that forces hand-offs. The quiet round is the common case, and in it every model token
is waste.

## Inventory

### The round frame (SKILL.md)

| What | Now | Can be | How |
|---|---|---|---|
| Slot check (`owner` slot, clean but for OWNER-ROLE.md), prerequisites, `due.py check` | model runs commands | D | `owner.py start-check` |
| Stay current: fetch, merge main into the slot, setup tasks if main changed | model | D | `owner.py tick` |
| The user's OWNER-ROLE.md edit: validate, commit or notify | model | D (notify: T) | tick |
| What is due, `due.py ran` after each item | model | D | tick |
| Loop scheduling (Claude CronCreate, `/owner` prompt every tick) | Claude cron, full skill load | D | **an external timer** (launchd/systemd) runs `owner.py tick`. The Claude session is woken (`hal2-cli-agents send <pane>`) only when the tick has items that need judgment |
| ListAgents, reading peer answers | model | J (reading free text) | only on a wake |
| Log entries | model calls `record` | D | every scripted action logs itself |
| Summary per round | model writes notes | D | from the log and the scans; `--notes` optional and only on a wake |
| Batched question to the user | model | T | tick collects the open items, the model pushes once on a wake (PushNotification is a model tool) |
| `/handoff` + `/clear` at 50% context | model | D (trigger) | a wake starts in a fresh, small context, so it is rarely needed |

### merge-to-main-boss

| What | Now | Can be | How |
|---|---|---|---|
| Snapshot and findings (`mtm_scan.py`) | D | D | already code |
| `priority`: move the slot to the front | model | D | tick runs `front` whenever a priority slot waits behind others |
| `held-idle` wake message | model writes it | T | fixed text with the failure, tests and slot |
| `held-idle` second round, no move: `worktree release` | model | D | rule: same ticket held-idle in two scans after a logged wake → release, log, notify the waiters (T) |
| `reserved-idle` → wake, then release | model | D/T | the same rule |
| `active-long`: read the landing's step | model | D | `hal2-cli-hooks landings <id>` → stuck past its timeout or dead pid → T message |
| `load-high`: tell busy slots to pause, then "go" | model | T | the list is code; send through `hal2-cli-agents send` with a fixed text |
| `waiter-gone` | model | T | fixed text |
| `flaky-candidate`: is it load-sensitive? | model | mostly D | rules: the message matches budget/timeout patterns, the load per core ≥ 2 at failure, and it passed elsewhere → ledger entry and a delegation brief; only unclear ones go to J |
| `work-not-queued`: what does it wait for? | model asks | J | needs reading the session's answer |
| `work-without-agent` with a `CURRENT_PLAN` and HANDOFF.md | model | D | `worktree run <NN> --detach --prompt "/handoff c"`; without HANDOFF.md → J |
| `long-queue` merge train | model | J | overlap analysis + carrier choice (the diff overlap could be D, the decision stays J) |
| Learn: reasons.md cases | model | J | (a signature match against known cases could be D) |

### development-lead

| What | Now | Can be | How |
|---|---|---|---|
| Classify sessions (`lead_scan.py`) | D | D | already code |
| `no-plan` | model sends | T | fixed text |
| `context-high` | model sends | T | fixed text (`/handoff`) |
| `idle-in-plan` that just stopped ("Next I'll…") | model | D/T | pattern on the last message → "continue the plan" text; the rest → J |
| `failed` without the watch duty | model | T | fixed resume text |
| `asks`: answer from INTENT/ADRs | model | J | reading and deciding |
| `blocked` permission prompts | model | J/T | J for which batch, T for the message |
| Review of a diff | model | J | |

### ci

| What | Now | Can be | How |
|---|---|---|---|
| Scan (`ci_scan.py`) | D | D | already code |
| Transient failure → `gh run rerun --failed` once | model reads the log | mostly D | regex over `gh run view --log-failed` (network, registry, runner lost, "The operation was canceled" ...) → rerun once per run, logged |
| `queued-long`: runner status | model | D | `gh api .../actions/runners` → offline runner named in the notice |
| `running-long`: no output 20 min → cancel + rerun once | model | D | |
| `slot-red` → tell the slot | model | T | fixed text with jobs and URL |
| A real failure → delegate | model | J (the brief) | the brief can be the evidence alone, since the worker does the thinking (see delegation) |

### sanity-watch (duty `watch`; the skill itself)

| What | Now | Can be | How |
|---|---|---|---|
| Scan and classify F1–F12 (`scan.py`) | D | D | already code |
| Resume F1–F3, F8 restore: the four preconditions, the prompt, waiting 90 s, `--key enter` | model | D | `scan.py resume <id>`: checks, sends, waits, records |
| F4 wait until the reset time | model | D | a time compare |
| F6, F7, F12 judge | model | J | (F7's two captures 60 s apart and the screen diff can be D) |
| Learn: the cases.md match | model | J (D for a known signature) | |
| Spawn the fix agent | model | T | the brief from evidence, the prompt template, `hal2-cli-agents spawn` |

### fix-autoclear (duty `autoclear`)

| What | Now | Can be | How |
|---|---|---|---|
| `evidence.py doctor` | D | D | already code |
| Restart a stuck session with a known continuation | model | D/T | for the known cases (soft stop, ignored hand-off) the text is fixed |
| Root-cause fix | model | J, in a worker | delegated |

### Delegation (SKILL.md "Delegate a fix")

| What | Now | Can be | How |
|---|---|---|---|
| Already in hand? Limit, free slot (`free.py`), new slot (`create.py`), the prompt, the log, follow-up "landed?", stopping the idle worker (`stop.py`) | model | D | `owner.py delegate --brief <file>`, `owner.py follow-up` |
| The brief | model writes it | T | evidence + finding + must-haves from a template; **the worker's plan and autogrill do the thinking**, not the owner |

### hal2's OWNER-ROLE.md tasks

| Task | Check | Act |
|---|---|---|
| n8n.hal9k.app stays up | D: curl + `hal2-cli-n8n instances check` | D: the redeploy command, plus a T notice |
| hal9k production healthy | D: `hal9k status` | T: a notice with the evidence |
| Disabled tests come back | D: ledger entries without a running plan | D: delegate (brief from the ledger line) |
| Orphaned slots finished | D: `work-without-agent` | D: `worktree run --detach --prompt "/handoff c"` |

The task format needs **machine-readable Check and Act**: a command in backticks is run by the tick (exit 0 =
fine). Act may be a command, `notify`, `delegate` or prose. Prose means a wake.

### Skills the workers use (not the owner's tokens, noted for later)

plan, grill/autogrill, mfm, mtm, create-shot, code-review: each has scripts already. Their remaining model work is
real judgment (writing plans, deciding branches, resolving conflicts). The mtm skill's steps 1–4 (reserve, commit,
gitignore junk) partly repeat `hal2-cli-git`. That is worth a later pass under the same ADR, outside this plan.

## The design that follows

1. **`owner.py tick`**, run by an **external timer**, not Claude's cron. It runs the round frame, every due duty's
   scan, every D action and every T action that a CLI can deliver (`hal2-cli-agents send` types the fixed text into
   an idle session's prompt). It writes the log and the summary.
2. It ends with **`needs_model`**: the J items, each with its evidence and the path of the one instruction file it
   needs. Empty: no model call at all. Otherwise it wakes the owner session with one short prompt, `/owner act`, and
   the session reads only the items file and their instruction files.
3. **The skill text splits**: SKILL.md shrinks to start/stop/act and the authority. Every finding kind gets a small
   `instructions/<kind>.md`, read only when its item is woken.
4. **Messages**: a T message to a session goes through `hal2-cli-agents send` (no model). The model's SendMessage
   is used only inside a wake, for J answers.

Expected: a quiet round costs **0** model tokens. A round with one J item costs that item's instruction file (1–3
KB) plus its evidence. That is roughly 90 % fewer tokens on a normal day.

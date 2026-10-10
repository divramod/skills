# Findings: other skills and repository docs

## Summary
- The scanned skills and repo files hold no mention of subservant, slot 30-99, plans/LEAD, `--parallel`, `plan.py`, `hal2-cli-agents switch` or `--model` for plan steps: nothing there depends on the old design.
- Only two places need a change: fix-autoclear (the effort re-apply is a single global value and cannot carry the coordinator's model, effort and window) and the README rows for plan/handoff (text describing the plan).
- Everything else is "no change"; two optional hardening items (list-free-worktrees, pause/continue) are noted.

## Per skill
| skill or file | change needed | what and where |
|---|---|---|
| adapt-merge-queue | no | only reads `plans/CURRENT_PLAN` (scripts/adapt.py:57-59) |
| adr | no | no hit |
| c | no | generated shortcut, runs `/handoff continue` (skills/c/SKILL.md:3,11); follows handoff changes automatically |
| h | no | generated shortcut for `/handoff` (skills/h/SKILL.md:3,11) |
| aliases.json | no | only maps h and c to handoff (lines 2-3) |
| cleanup | no | skips `CURRENT_PLAN` and tracked handoff.md (SKILL.md:34,40) |
| continue | optional | resumes subagents by SendMessage (SKILL.md:40) and rewrites CURRENT_PLAN (:55). With all steps in subagents, a paused coordinator has many running step subagents; the existing text covers it. Optionally add: restore the coordinator's model/effort/window from plan.md |
| continue-all-agent-work | no | no hit |
| create-shot | no | only says it writes no CURRENT_PLAN (SKILL.md:11); idle-slot rule at :126 uses "no plan in CURRENT_PLAN" |
| delete-worktree-session | no | no LEAD or slot-30 logic; scripts/stop.py:10 only refuses on a clear-and-continue job. A subservant slot would be stoppable like any slot; once subservants go, nothing to remove |
| digest-todolist-picture | no | scripts/implement.py:41 tells the session to `/plan new`; the plan skill's change flows in |
| fix-autoclear | yes | SKILL.md:147,171-177 (and :157, :203): the job restores effort from one global `[autoclear] effort` setting via `/effort <level>`, reading the screen; no model, no window. For (c) the clear-and-continue must read the coordinator's model/effort/window from plan.md (or `/handoff c` must re-apply them): add a section "coordinator settings after a clear", update the busy path note (:157, "No `/effort` on this path"), which would lose effort for a busy coordinator. The code lives in hal2 (autoclear/effort.rs), not in this repo: only the skill's knowledge and `cases.md` change here. `/effort` also rewrites the user's default in `~/.claude/settings.json` (:177), a trap when the plan's effort differs per plan |
| list-free-worktrees | no (optional) | scripts/free.py:6-9,76-84 treats all slots alike (agent not busy, no CURRENT_PLAN, no uncommitted work, nothing unmerged); no LEAD/30+ special case, so no edit needed. Subservant slots are currently reported "free" once idle with no CURRENT_PLAN (they carry LEAD instead); gone with the new design |
| mfm | no | no hit |
| mtm-fastlane | no | only lists CURRENT_PLAN in the report (SKILL.md:68) |
| pause | optional | SKILL.md:27 records subagents (id, task, last report); pause record at :60-69 stores the CURRENT_PLAN name. Add the coordinator's model/effort/window there only if the plan does not hold it (it will, per (c)) |
| stop-all-agent-work | no | delegates to `/pause` (SKILL.md:33) |
| tell | no | uses subagents only for summarising (SKILL.md:64,72; subskills/topic/SUBSKILL.md:56,63) and `--model <your model id>` for note metadata (:117,143): unrelated to plan steps |
| README.md | yes | table rows for plan (line 12), handoff (line 11), also pause/continue (16-17) and list-free-worktrees (29) are summaries; plan row must drop "subservants in slots 30-99" and gain "steps sized by Model/Effort/Window", create-worktree-session's row likewise if it mentions a parallel subservant. Update once the plan skill is changed |
| AGENTS.md | no | no hit |
| CLAUDE.md | no | no hit; its "Skill script rules" only forbid scripts starting sessions themselves |
| docs/ | no | one hit, docs/selfimprovement/common/finalize-detach-commit-mints-plan.md:15, an old CURRENT_PLAN breadcrumb |
| scripts/check-agent-starts.py | no (optional) | line 7 lists create-worktree-session's create.py as a legitimate session starter; if create.py loses its `--lead` mode the allowed list does not change |
| scripts/install-skills.py, gen-aliases.py, link-skills.sh, check-plugins.py | no | no hit for any search term |

## Notes
- Surprise: none of the scanned skills mention plans/LEAD. The marker is known only to plan, create-worktree-session and mtm, so removing subservants has no ripple here.
- The one real gap is fix-autoclear: effort survives a clear only through the global hal2 `[autoclear] effort` setting, and not at all on the busy path (SKILL.md:157), where it is logged "No /effort on this path". Model and window are never re-applied at all. Target (c) therefore needs hal2 code (reading plan.md) and a skill note; the repository holds only the skill text.
- The farmer-side `/farmer handoff` kind (fix-autoclear SKILL.md:111-114) uses a different handoff command; not a plan coordinator, so unaffected.
- Plans cleaned by the new rule apply to "the plan folder's own handoff.md" (fix-autoclear :113): if coordinator settings go into plan.md, the hand-off freshness check is unaffected.

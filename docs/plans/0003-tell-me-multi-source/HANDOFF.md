---
plan: 0003-tell-me-multi-source
phase: 005-x-source
chain_next: /hal-lc-auto 0003
session_only:
  - Shipped - 001, 002, 003, 004 (fixes f1caed9, shipped 39aaf08)
  - 005 x - built+tested 5314c0a; review done, a fix agent was working on 13 findings (x/, video/prepare|download_video|migrate_library, subskills/x). If no `fix(tell-me): x review` commit exists, re-run the fixes from the review list (context lost with the agent), then flip reviewed/shipped + `hal plan phase ship --phase 005`
  - 006 file - built+tested 84aaf87; review found 3 critical (stale summary on a changed file, reused path overwrites an unrelated doc, alias ping-pong) + pdftotext-first etc; fix agent running (scripts/file, subskills/file, SKILL.md summary_exists bullet, web/extract.py quoting, route DOC_EXT). Check for a `fix(tell-me): file review` commit
  - 007 multi-input - built+tested f20eb68, review fixes committed cba8a01. STILL TODO in SKILL.md (held back to avoid clobbering the file fixer's SKILL.md edit) - (a) an item with exit_code 2 -> run that source's install-prerequisites.sh and prepare it again; (b) a playlist/channel item among several inputs -> handle its videos + its own digest first, then the combined digest; (c) "all inputs first, then the flags" rule in step 1 (line ~45 still singular). Then ship 007
  - 008 UI+docs - T701-T703 built+tested e9c33e2 (panels.py, sidebar chips, README, plugin 0.3.0); review agent running. T704 final e2e + verify-success.sh (hal plan spec render-verify) still to do after 005-007 ship
  - Scratch libraries for E2E live under the session scratchpad (lib-x, lib-file, lib-multi, lib-all) - never ~/me/summaries
  - Real library ~/me/summaries/videos is NOT migrated - at the end tell the user to run scripts/video/migrate_library.py --apply
  - Tell the user - testing the migration on a copy once sent SIGTERM to their library server pid 72144 (fixed since; --open restarts it)
  - FxTwitter facts (2026-09-25) - /2/thread of a mid-self-thread post starts at that post; /2/conversation cursor pages answer 404; first page sometimes empty
  - SELFIMPROVEMENT - SI-0001 at 3 occurrences (ADR-worthy); SI-0002 (avoid-drift `goals show --plan`) now 2
---

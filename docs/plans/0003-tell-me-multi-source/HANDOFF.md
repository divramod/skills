---
plan: 0003-tell-me-multi-source
phase: 004-github-source
chain_next: /hal-lc-auto 0003
session_only:
  - Phase 003 shipped (review fixes 4b7604e). Phase 004 github built+tested (50b83ef); its independent review was STILL RUNNING at handoff - re-run a code-reviewer subagent on `git show 50b83ef`, fix findings, flip reviewed/shipped (hal plan update), `hal plan phase ship --plan 0003-tell-me-multi-source --phase 004`, then /hal-lc-avoid-drift
  - Phase 005 x not started. Probed live - FxTwitter `api.fxtwitter.com/2/thread/<id>` and `/2/status/<id>` work (shape - {status, thread?, ...}); `/2/conversation/<id>` returned code 404 for jack/20 (old post) - re-probe with a recent post with replies before designing client.py; v1 `api.fxtwitter.com/<user>/status/<id>` also works ({code, tweet})
  - Verify loop note - `unittest discover` exits 5 on NO TESTS RAN (file/, x/ have no tests yet); run folders individually until 005/006 add tests
  - Real library ~/me/summaries/videos is NOT migrated - at the end tell the user to run scripts/video/migrate_library.py --apply
  - Tell the user - testing the migration on a copy once sent SIGTERM to their library server pid 72144 (fixed since; --open restarts it)
  - SELFIMPROVEMENT - SI-0001 bumped to 3 occurrences (ADR-worthy), SI-0002 open
---

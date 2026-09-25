---
plan: 0003-tell-me-multi-source
phase: 002-web-source
chain_next: /hal-lc-auto 0003
session_only:
  - WIP (untracked, works on a real post, no tests yet) skills/tell-me/scripts/web/{extract.py,prepare.py,fixtures/}; T101/T102 code exists, next write test_extract.py + test_prepare.py from fixtures/
  - web/prepare.py must use unique_dir(meta) instead of dir_for(meta) (new in _common after the 001 review)
  - Every source uses sys.path.append (not insert) for scripts/shared; tests run via scripts/run-tests.sh
  - Review each phase with an independent code-reviewer subagent before shipping (large tier)
  - User's real library ~/me/summaries/videos is NOT migrated yet: at the end tell them to run scripts/video/migrate_library.py --apply
  - Tell the user: testing the migration on a copy once sent SIGTERM to their library server pid 72144 (fixed since; --open restarts it)
---

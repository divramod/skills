---
plan: 0003-tell-me-multi-source
phase: 003-hn-source
chain_next: /hal-lc-auto 0003
session_only:
  - Phase 002 shipped (eeb0476) after 3 review rounds (717328c, 865006d, ba2a6e4; final APPROVE). Drift check at the boundary - no drift
  - Phase 003 (hn) in progress, uncommitted - shared/check_quotes.py + test (T202 built, 6 tests green); hn/prepare.py (T201 built, live-verified on item 42460143 -> story 42457213; needs fixtures + tests); next T203 hn/related.py, T204 subskill/template, T205 prereqs (uvx/npx for the article) + e2e (link post + Ask HN e.g. 4102013)
  - e2e libraries (not the user's) - scratchpad lib/ (2 saved summaries) and lib2/
  - User's real library ~/me/summaries/videos is NOT migrated yet - at the end tell them to run scripts/video/migrate_library.py --apply
  - Tell the user - testing the migration on a copy once sent SIGTERM to their library server pid 72144 (fixed since; --open restarts it)
---

---
plan: 0003-tell-me-multi-source
phase: 002-web-source
chain_next: /hal-lc-auto 0003
session_only:
  - T101-T105 built+tested (a22e28e); review round 1 fixed in 717328c; round 2 (1 major, 10 minor, 2 nits) fixed in 865006d. Next - confirm round-3 re-review of 865006d, then flip reviewed/shipped and ship phase 002
  - Sphinx heading anchors fixed (ids from permalink href / section id) and verified live on docs.python.org regex howto (26 [#])
  - Wayback live - IA answered again; geocities URLs exercise soft-404 + consent-wall paths live. Soft-404 (deep link -> home page) and consent/login walls are now detected
  - e2e libraries (not the user's) - scratchpad lib/ (2 saved summaries) and lib2/
  - User's real library ~/me/summaries/videos is NOT migrated yet - at the end tell them to run scripts/video/migrate_library.py --apply
  - Tell the user - testing the migration on a copy once sent SIGTERM to their library server pid 72144 (fixed since; --open restarts it)
---

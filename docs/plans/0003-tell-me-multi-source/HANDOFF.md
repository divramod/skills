---
plan: 0003-tell-me-multi-source
phase: 002-web-source
chain_next: /hal-lc-auto 0003
session_only:
  - T101-T105 built+tested (a22e28e); 15 review findings fixed in 717328c. Next - re-review 717328c with an independent code-reviewer subagent, then flip reviewed/shipped and ship phase 002
  - Open check - on docs.python.org/3/howto/regex.html trafilatura won and content.md got no heading [#] anchors; verify trafilatura keeps Sphinx headings (else prefer the extractor that keeps them)
  - Wayback lookups returned empty / "Temporarily Offline" on 2026-09-25, so the live Wayback path is only fixture-tested; retry one dead URL live when IA is up
  - e2e libraries (not the user's) - scratchpad lib/ (2 saved summaries) and lib2/
  - User's real library ~/me/summaries/videos is NOT migrated yet - at the end tell them to run scripts/video/migrate_library.py --apply
  - Tell the user - testing the migration on a copy once sent SIGTERM to their library server pid 72144 (fixed since; --open restarts it)
---

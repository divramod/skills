---
plan: 0003-tell-me-multi-source
phase: 006-file-source
chain_next: /hal-lc-auto 0003
session_only:
  - Shipped - 001-005 (005 fixes 2b8079f, shipped 156cef0)
  - 006 file - built+tested 84aaf87. Review found 3 critical (stale summary on a changed file, a reused path overwrites an unrelated doc, alias ping-pong) + pdftotext-first, layout-title, streaming size cap, PDF clean-up, rtf/doc, encodings. A fix agent was still running at handoff. If `git log` has a `fix(tell-me): file review` commit, verify tests and ship 006; else redo the fixes (code-review subagent on 84aaf87 to get the list back)
  - 007 multi-input - built+tested f20eb68, review fixes cba8a01. Before shipping, add to SKILL.md - (a) an item with exit_code 2 -> run that source's install-prerequisites.sh, prepare it again; (b) a playlist/channel item among several inputs -> its videos + own digest first, then the combined digest; (c) step 1 - all inputs first, then the flags (line ~45 still says "the input")
  - 008 UI+docs - T701-T703 built+tested e9c33e2; review done (request changes) -> fix everything in phases/008-library-ui-and-docs/review.md, then T704 - final e2e one input per source + `hal plan spec render-verify`
  - Known nit - in the x flow the video source's reuse log says "pass --refresh"; for x it is --refresh-video
  - E2E scratch libraries were in the old session's scratchpad; use a new scratch TELL_ME_ROOT, never ~/me/summaries
  - At the end tell the user - ~/me/summaries/videos is NOT migrated (run scripts/video/migrate_library.py --apply); a migration test once SIGTERMed their library server pid 72144 (fixed; --open restarts it)
  - FxTwitter (2026-09-25) - conversation cursor pages 404, the first page is sometimes empty, the thread length is flaky between calls
  - SELFIMPROVEMENT - SI-0001 at 3 occurrences (ADR-worthy); SI-0002 (avoid-drift `goals show --plan`) at 2
---

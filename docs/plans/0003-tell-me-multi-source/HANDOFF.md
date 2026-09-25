---
plan: 0003-tell-me-multi-source
phase: 003-hn-source
chain_next: /hal-lc-auto 0003
session_only:
  - Phase 002 shipped (eeb0476). Phase 003 hn built+tested (2086f9a); its independent review was STOPPED at handoff - re-run a code-reviewer subagent on `git show 2086f9a`, fix findings, flip reviewed/shipped, `hal plan phase ship --plan 0003-tell-me-multi-source --phase 003`, then mfm + /hal-lc-avoid-drift
  - Phase 004 github WIP is UNCOMMITTED and untested in skills/tell-me/scripts/github/ - client.py (gh or REST, live-verified), anchors.py ([L<n>] ?plain=1 line anchors + GitHub heading slugs), prepare.py (repo path; imports thread.py which does not exist yet), fixtures/ (kepano/defuddle). REPOMIX pin repomix@1.4.2 is a guess - verify with `npm view repomix version`. Still to do - thread.py (issues/PRs/discussions via graphql), related.py, tests, SUBSKILL/template, e2e
  - Real library ~/me/summaries/videos is NOT migrated - at the end tell the user to run scripts/video/migrate_library.py --apply
  - Tell the user - testing the migration on a copy once sent SIGTERM to their library server pid 72144 (fixed since; --open restarts it)
  - Captured SELFIMPROVEMENT records this session - SI-0001 (bumped), SI-0002
---

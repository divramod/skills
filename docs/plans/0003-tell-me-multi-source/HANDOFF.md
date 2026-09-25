---
name: handoff
description: Living automode checkpoint for 0003-tell-me-multi-source.
---

# Handoff — 0003-tell-me-multi-source (automode, living checkpoint)

Resume: `/a 0003`

## Where we are

- Phase 001 (restructure-and-contract) **shipped** (commits 9cb5e0e..b4abeea, review fixes in 6cf6e8d).
- Phase 002 (web-source) **in progress**: `scripts/web/extract.py`, `scripts/web/prepare.py` and
  `scripts/web/fixtures/` exist (uncommitted when this was written) and work on a real post; next: tests
  (`test_extract.py`, `test_prepare.py` with fixtures), SUBSKILL/template, e2e on 2 posts (one JS-heavy).

## Decisions made during 001 (not in the spec)

- `sys.path.append` (not insert) of `scripts/shared` in source scripts: `prepare.py` exists in both
  `shared/` and each source folder, and the source's own folder must win.
- `scripts/run-tests.sh` runs each folder's tests in its own interpreter and skips folders without tests
  (`unittest discover` exits 5 on "no tests"). Spec success criteria use it.
- Frontmatter of `summary.md` is source-neutral now (`author`, `site`, `id`, `extractor`, `source`);
  `render_html` still reads the old `channel`/`platform` keys of existing notes.
- `library.js` entries carry `source`, `group` (the channel/site/owner folder) and `group_name`; the sidebar
  labels group folders with `group_name`. Phase 008 builds the source filter on `source`.
- `unique_dir(meta)` adds a 6-char id hash when a folder already holds another item — use it in every source.
- Unbuilt URL sources fall back to the video source (yt-dlp) in `shared/prepare.py`.
- Old video folders are migrated on touch (`video/migrate_library.migrate_folder`) and `shared/prepare.py`
  warns when any remain; the user's real library (~/me/summaries/videos, 4 folders) is NOT migrated yet —
  tell the user to run `scripts/video/migrate_library.py --apply` at the end.
- While testing the migration on a copy, its apply run tried to stop the pid in the copied `.server.json`
  (the user's library server, 8765). Fixed (`serves()` checks the command line). Mention it to the user.

## Open threads

- Review each phase with an independent code-reviewer subagent before shipping (large tier).
- Wave-02 phases (002, 004, 005, 006, 007) only touch their own folders (+ 007: shared/prepare.py, digest).

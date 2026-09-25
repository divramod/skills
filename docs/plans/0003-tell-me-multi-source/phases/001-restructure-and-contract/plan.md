---
name: restructure-and-contract
description: Move tell-me to subskills/scripts/templates with shared/, add the router + source contract + per-folder prereqs; video only, no regressions.
status: approved
phase_id: "001"
depends_on: []
wave: "01"
created: 2026-09-25
tier: large
tier_source: manual
---

## Overview

Restructure without new behaviour. Afterwards the video flow works exactly as before, but through the router and the contract, and every shared file already knows all six sources, so the wave-02 phases only add their own folders.

## Architecture

`scripts/shared/prepare.py <input>` → `route.py` → `scripts/<source>/prepare.py` (subprocess) → JSON envelope
`{source, dir, summary_exists, subskill, template, content_file, …}`. Sources that are not built yet exit 1 with
`source '<s>' not supported yet`. The shared scripts (`save_summary`, `render_html`, `library`, `check_links`,
`serve_library`) read only the contract fields from `metadata.json`. `render_html` gets a
`HEADER_PANELS = {source: fn}` dispatch; video's panel is today's player.

## Approach

`git mv` first (keeps history) and fix imports until the old tests pass. Then add route/contract, then the migration, then rewrite SKILL.md, then the prereq/check-plugins rule. Commit after each task that leaves tests green.

## Tasks

- [ ] **T001** — `git mv` scripts into `scripts/shared/` + `scripts/video/`; `prepare_video.py`→`video/prepare.py`, `similar_videos.py`→`video/related.py`; sys.path bootstrap; serve_library calls video download via subprocess
  **Acceptance**: all existing tests pass from their new folders; no import of a video module from shared/; `serve_library.py` uses `video/download_video.py --status/--delete/--background` (add `--status` JSON output) instead of importing `download_status`/`delete_video`/`start_background`
  **Verify**: `cd skills/tell-me/scripts && for d in */; do python3 -m unittest discover -s "$d" -p 'test_*.py' || exit 1; done`
  **Files**: skills/tell-me/scripts/**
  **Size**: L
  **State**:
  - [x] built
  - [ ] tested
  - [ ] reviewed
  - [ ] shipped

- [ ] **T002** — `shared/route.py`: classify input → {source, id, url|path, kind} for all six sources (+ github issue/pull/discussion kinds, x/twitter/fixupx/vxtwitter hosts, yt-dlp-supported → video, else http → web)
  **Acceptance**: table test with ≥25 inputs passes; unknown scheme exits 1
  **Verify**: `python3 -m unittest discover -s skills/tell-me/scripts/shared -p test_route.py`
  **Files**: skills/tell-me/scripts/shared/route.py, test_route.py
  **Size**: M
  **State**:
  - [ ] built
  - [ ] tested
  - [ ] reviewed
  - [ ] shipped

- [ ] **T003** — `shared/prepare.py` dispatcher + contract: shared metadata fields (`source,id,url,title,author,published,fetched,site,word_count,duration,extractor,content_file,extras`), envelope with `subskill`/`template`; stub exit for unbuilt sources
  **Acceptance**: video URL prints the same data as before plus contract fields; `https://example.com` prints `not supported yet` exit 1
  **Verify**: unit test with a fake source module + manual run on a cached YouTube folder
  **Files**: skills/tell-me/scripts/shared/prepare.py, _common.py, test_prepare.py, scripts/video/prepare.py
  **Size**: M
  **State**:
  - [ ] built
  - [ ] tested
  - [ ] reviewed
  - [ ] shipped

- [ ] **T004** — Library root → `~/me/summaries` (`TELL_ME_ROOT`, fallback parent of `DM_SUMMARIZE_VIDEO_ROOT`); folder per kind (`videos/`, `articles/`, `repos/`, `posts/`, `discussions/`, `documents/`); `library.js` at the root
  **Acceptance**: existing video folders resolve unchanged; `library.py --pages` on a temp copy re-renders with a working sidebar
  **Verify**: unit tests for `library_root`, `dir_for(meta)` per source
  **Files**: skills/tell-me/scripts/shared/_common.py, library.py, render_html.py, serve_library.py
  **Size**: M
  **State**:
  - [ ] built
  - [ ] tested
  - [ ] reviewed
  - [ ] shipped

- [ ] **T005** — `transcript.md` → `content.md` everywhere + `video/migrate_library.py` (dry-run default, `--apply`, idempotent, re-renders pages)
  **Acceptance**: migration test on a temp library; second run no-op; no `transcript.md` in scripts except migrate/tests
  **Verify**: unittest + `grep` success criterion
  **Files**: skills/tell-me/scripts/video/migrate_library.py, test_migrate_library.py, scripts/**
  **Size**: M
  **State**:
  - [ ] built
  - [ ] tested
  - [ ] reviewed
  - [ ] shipped

- [ ] **T006** — Templates: `templates/shared/{summary,tldr,detailed,wisdom,qa,digest,links}.md` made source-neutral ("anchor link from the content file"); `templates/video/template.md` holds chapters mode + Similar videos
  **Acceptance**: no template in shared/ mentions video/timestamp specifics
  **Verify**: `grep -il 'timestamp\|video' templates/shared/*.md` is empty
  **Files**: skills/tell-me/templates/**
  **Size**: S
  **State**:
  - [ ] built
  - [ ] tested
  - [ ] reviewed
  - [ ] shipped

- [ ] **T007** — SKILL.md → router (<200 lines): no-link, prepare, read `subskills/<source>/SUBSKILL.md`, modes, write, links, save; `subskills/shared/{links,discussion}.md`; `subskills/video/SUBSKILL.md` (visual, download, Whisper, playlists); stub SUBSKILL.md + template.md for web/github/x/hn/file
  **Acceptance**: every source's SUBSKILL.md linked from SKILL.md; frontmatter description covers all sources; SKILL.md < 500 lines
  **Verify**: spec success criteria 4–6
  **Files**: skills/tell-me/SKILL.md, skills/tell-me/subskills/**, skills/tell-me/templates/*/template.md
  **Size**: M
  **State**:
  - [ ] built
  - [ ] tested
  - [ ] reviewed
  - [ ] shipped

- [ ] **T008** — Per-folder prereqs: `scripts/{shared,video}/check-/install-prerequisites.sh`, stubs for other sources, top-level aggregators `--source x`; `require()` hint names the source's install script; `check-plugins.py` per-folder rule + test; CLAUDE.md/AGENTS.md rule text
  **Acceptance**: `check-plugins.py` passes; removing a source's prereq script makes it fail
  **Verify**: `python3 scripts/check-plugins.py` + its new test
  **Files**: skills/tell-me/scripts/*/*-prerequisites.sh, skills/tell-me/scripts/*-prerequisites.sh, scripts/check-plugins.py, CLAUDE.md, AGENTS.md
  **Size**: M
  **State**:
  - [ ] built
  - [ ] tested
  - [ ] reviewed
  - [ ] shipped

- [ ] **T009** — Update spec success-criteria test command to the per-folder loop; e2e: summarize one real YouTube video end to end on a temp root
  **Acceptance**: summary.html opens in the library with the player, content.md, links with dates
  **Verify**: manual e2e + `hal plan spec render-verify`
  **Files**: docs/plans/0003-tell-me-multi-source/spec.md
  **Size**: S
  **State**:
  - [ ] built
  - [ ] tested
  - [ ] reviewed
  - [ ] shipped

## Risks

Import breakage after `git mv`, and the shared→video coupling in serve_library. Old pages keep pointing at the old library.js until they are re-rendered.

## Open Questions

None.

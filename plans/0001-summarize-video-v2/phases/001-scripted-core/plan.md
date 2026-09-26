---
name: scripted-core
description: Move deterministic work to scripts; library folder; --download; reuse by ID; save_summary with frontmatter; tool checks.
status: shipped
schema_version: 1
phase_id: '001'
depends_on: []
wave: 1
created: '2026-09-25'
tier: medium
---

## Overview

Replace `fetch_transcript.py` with `_common.py` + `prepare_video.py` + `save_summary.py`.

## Architecture

`prepare_video.py` resolves metadata, then the folder (reusing an existing one via `metadata.json` ID lookup), the transcript,
the optional video download and the optional frames. It prints one JSON object that the agent reads.

## Approach

Keep the proven caption and Whisper logic. When a video file already exists, Whisper transcribes it instead of downloading the audio again.

## Tasks

- [x] **T001** — `_common.py`: root/platform/user/slug resolution, ID lookup, `require()`, yt-dlp base, ts + link helpers
  **Acceptance**: unit tests for slug, folder resolution and lookup pass. **Verify**: unittest. **Files**: scripts/_common.py, scripts/test_common.py. **Size**: M
- [x] **T002** — `prepare_video.py` with `-d/--download`, `--refresh`, JSON output; remove `fetch_transcript.py`
  **Acceptance**: a local mp4 run creates the folder with transcript.md, metadata.json and video.mp4. **Verify**: e2e script. **Files**: scripts/prepare_video.py. **Size**: L
- [x] **T003** — `save_summary.py`: stdin body → summary.md with frontmatter + header
  **Acceptance**: the frontmatter test passes. **Verify**: unittest. **Files**: scripts/save_summary.py, scripts/test_save_summary.py. **Size**: S
- [x] **T004** — Rewrite SKILL.md to keep only the non-deterministic steps
  **Acceptance**: SKILL.md contains no inline shell logic beyond script calls. **Verify**: review. **Files**: SKILL.md. **Size**: S

## Risks

- YouTube rate limits during the live test, mitigated by the local e2e fixture.

## Open Questions

None.


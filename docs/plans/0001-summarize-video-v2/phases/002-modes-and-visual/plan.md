---
name: modes-and-visual
description: Summary mode templates with ready-made timestamp links; ffmpeg scene keyframes.
status: shipped
phase_id: "002"
depends_on: ["001"]
wave: "02"
tier: medium
---

## Overview

Idea 1 (modes) and idea 3 (visual pass).

## Architecture

Transcript paragraphs and chapter lists render `[mm:ss](url&t=Ns)` links. `extract_frames.py` runs ffmpeg
`select='gt(scene,T)'` + `showinfo`, parses the `pts_time` values, caps the count by even subsampling, and falls back to fixed intervals.

## Approach

The templates are plain markdown files, and SKILL.md tells the agent which one to use.

## Tasks

- [x] **T001** — Timestamp links in transcript.md (platform-aware)
  **Acceptance**: the links test passes for watch?v=, youtu.be and non-YouTube URLs. **Verify**: unittest. **Files**: _common.py, prepare_video.py. **Size**: S
- [x] **T002** — templates/{tldr,summary,chapters,detailed,wisdom,qa}.md
  **Acceptance**: all six exist and are referenced in SKILL.md. **Verify**: ls. **Files**: templates/. **Size**: S
- [x] **T003** — `extract_frames.py` + `--visual` in prepare_video
  **Acceptance**: the local e2e run writes frames/*.jpg + index.md, at most --max frames. **Verify**: e2e + unittest. **Files**: scripts/extract_frames.py, scripts/test_extract_frames.py. **Size**: M

## Risks

- A static video (slides) can yield 0 scene changes; mitigated by the interval fallback.

## Open Questions

None.

---
name: multi-input-digest
description: Multiple inputs in one call and a generalized digest across any sources.
status: shipped
schema_version: 1
phase_id: '007'
depends_on:
- '001'
wave: 2
created: '2026-09-25'
tier: large
tier_source: manual
---

## Overview

`tell-me <a> <b> <c>` prepares each input and offers a digest across them.

## Architecture

`shared/prepare.py` accepts N inputs and prints a JSON list of envelopes plus a `digest_dir` (`<root>/digests/<date>-<slug>/`, as `list_videos.py` does for playlists). SKILL.md: more than 3 inputs → parallel subagents; then the digest, whose template is generalized from the playlist digest (rank by worth, shared themes, disagreements).

## Approach

Reuse the existing digest folder/metadata logic from `list_videos.py` by moving it into `shared/_common.py` as `digest_dir()`. `list_videos.py` keeps its CLI unchanged (a one-line import change), so it doesn't conflict with 005.

## Tasks

- [x] **T601** — N-input prepare + digest folder
  **Acceptance**: unit test: 2 fixture inputs → 2 envelopes + digest_dir
  **Verify**: `cd skills/tell-me/scripts && for d in */; do python3 -m unittest discover -s "$d" -p 'test_*.py' || exit 1; done`
  **Files**: skills/tell-me/scripts/shared/prepare.py
  **Size**: S
  **State**:
  - [x] built
  - [x] tested
  - [x] reviewed
  - [x] shipped

- [x] **T602** — Generalize `templates/shared/digest.md` + SKILL.md step (multi-input and playlists share it)
  **Acceptance**: review
  **Verify**: review
  **Files**: skills/tell-me/templates/shared/digest.md, SKILL.md
  **Size**: S
  **State**:
  - [x] built
  - [x] tested
  - [x] reviewed
  - [x] shipped

- [x] **T603** — E2E: a video + an article + an HN post in one call
  **Acceptance**: 3 summaries + digest page
  **Verify**: manual
  **Files**: –
  **Size**: S
  **State**:
  - [x] built
  - [x] tested
  - [x] reviewed
  - [x] shipped

## Risks

Wave-02 overlap: edits `shared/prepare.py` and SKILL.md. Keep the diff small and rebase last in the wave.

## Open Questions

None.


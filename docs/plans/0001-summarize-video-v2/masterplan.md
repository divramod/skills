---
name: summarize-video-v2
description: Masterplan for dm-summarize-video v2 (scripted core, library folder, -d, modes, visual pass, playlists, prerequisite rules).
status: shipped
created: 2026-09-25
tier: medium
---

# Masterplan: summarize-video-v2

## Overview

There are three phases, each testable on its own. Phase 001 moves all deterministic work into scripts and introduces the
permanent library folder plus `-d`. Phase 002 adds modes with timestamp links and the visual pass. Phase 003 adds
playlist/channel digests, prerequisite scripts and the repo-wide script rules. See [spec.md](spec.md).

## Phase List

| Phase | Slug | Goals | Depends on | Wave |
|-------|------|-------|------------|------|
| 001 | scripted-core | G1, G2, G4, G7, G8 | – | 01 |
| 002 | modes-and-visual | G3, G5 | 001 | 02 |
| 003 | playlists-and-rules | G6, G9 | 001 | 02 |

## Waves

- Wave 01: 001
- Wave 02: 002, 003 (independent files; can run in parallel)

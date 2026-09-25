---
name: playlists-and-rules
description: Playlist/channel expansion + digest folder; check/install prerequisite scripts; repo rules in CLAUDE.md/AGENTS.md enforced by check-plugins.
status: shipped
phase_id: "003"
depends_on: ["001"]
wave: "02"
tier: medium
---

## Overview

Idea 4 plus the shot-5 prerequisite rules.

## Architecture

`list_videos.py` uses `yt-dlp --flat-playlist -J` (`--playlist-end N` for channels) and writes the digest folder's metadata.json.

## Approach

Bash prerequisite scripts; `check-plugins.py` flags a skill whose scripts call external tools but lack the two scripts.

## Tasks

- [x] **T001** — `list_videos.py` + digest folder
  **Acceptance**: the flat-playlist JSON parsing test passes. **Verify**: unittest. **Files**: scripts/list_videos.py, scripts/test_list_videos.py. **Size**: M
- [x] **T002** — `check-prerequisites.sh` / `install-prerequisites.sh`
  **Acceptance**: check exits 0 here and 1 with a clear message when PATH lacks the tools. **Verify**: run with a stripped PATH. **Files**: scripts/*.sh. **Size**: S
- [x] **T003** — Script rules in CLAUDE.md + AGENTS.md; enforcement in scripts/check-plugins.py; README + version bump
  **Acceptance**: check-plugins passes, and fails when a prerequisite script is removed. **Verify**: run both. **Files**: CLAUDE.md, AGENTS.md, scripts/check-plugins.py, README.md, plugin.json x2. **Size**: S

## Risks

- hal may regenerate CLAUDE.md/AGENTS.md; the enforcement lives in check-plugins.py as well.

## Open Questions

None.

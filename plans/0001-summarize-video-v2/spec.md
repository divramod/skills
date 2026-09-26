---
name: summarize-video-v2
description: dm-summarize-video v2 — deterministic work moved into scripts, permanent library at ~/me/summaries/videos, --download, summary modes, visual pass, playlist/channel digests, prerequisite scripts + repo-wide script rules.
status: shipped
schema_version: 1
created: '2026-09-25'
approved: '2026-09-25'
shipped: '2026-09-25'
tier: medium
tier_source: manual
---


# Spec: summarize-video-v2

## Objective

Make `skills/dm-summarize-video` a reliable, mostly scripted pipeline. Everything deterministic
(fetching, paths, downloads, timestamp links, frame extraction, playlist expansion, file writing,
prerequisite checks) lives in `scripts/`. `SKILL.md` keeps only the judgment work: picking a mode,
writing the summary, fixing mishearings, reading frames, ranking videos.
Every summary lands in a permanent, browsable library:
`~/me/summaries/videos/<platform>/<user>/<title>/`.

The five improvement ideas from the shot-3 research are in scope (G3–G7), plus the shot-5 asks (G1, G2, G8, G9).

## Goals

| ID | Tier | Goal (GQM purpose/object) | Done criterion (EARS) |
|----|------|---------------------------|-----------------------|
| G1 | must | Store every summary in a permanent per-video folder | WHEN a video is prepared, the system SHALL use `<root>/<platform>/<user>/<title-slug>/` (root default `~/me/summaries/videos`, env `DM_SUMMARIZE_VIDEO_ROOT`) holding `transcript.md`, `metadata.json`, and after saving, `summary.md` |
| G2 | must | Download the video on request | WHEN `--download`/`-d` is passed, the system SHALL save the video in the highest available quality (no height cap; mp4, else mkv, no re-encoding) as `video.<ext>` in the same folder, replacing a lower-quality copy (e.g. the ≤1080p one `--visual` alone fetches) |
| G3 | must | Summary modes (idea 1) | The skill SHALL support modes `tldr`, `summary` (default), `chapters`, `detailed`, `wisdom`, `qa`, each with a template in `templates/`, and transcript paragraphs/chapters SHALL carry ready-made timestamp links |
| G4 | must | Reuse by video ID (idea 2) | WHEN a video whose ID already has a folder is prepared again, the system SHALL reuse that folder and its transcript without network transcript fetches unless `--refresh` |
| G5 | should | Visual pass (idea 3) | WHEN `--visual` is passed, the system SHALL extract ≤ N (default 40) scene-change keyframes into `frames/` with an `index.md` of timestamps |
| G6 | should | Playlists and channels (idea 4) | WHEN given a playlist or channel URL, `list_videos.py` SHALL emit the video list (channel: latest `--limit` N) and create a digest folder for `digest.md` |
| G7 | must | Save and deliver with frontmatter and translation (idea 5) | `save_summary.py` SHALL write `summary.md` with YAML frontmatter (title, channel, url, published, duration, platform, video_id, mode, lang, transcript_source, created) and the summary SHALL be writable in any language (`--summary-lang`) |
| G8 | must | Scripts check their external tools | Every script that calls an external tool SHALL check for it first and exit non-zero with a clear message naming the tool and the install command |
| G9 | must | Prerequisite scripts per skill + repo rule | Every skill whose scripts use external tools SHALL ship `scripts/check-prerequisites.sh` and `scripts/install-prerequisites.sh`; the rule SHALL be documented in `CLAUDE.md` + `AGENTS.md` and enforced by `scripts/check-plugins.py` |

## Non-Goals

| ID | Non-goal |
|----|----------|
| G-N1 | No paid APIs or LLM calls from scripts (the agent summarizes; the Gemini visual pass stays out of scope) |
| G-N2 | No migration of the old `~/.cache/dm-summarize-video` cache (it is just a cache) |
| G-N3 | No speaker diarization |
| G-N4 | No fully unattended batch summarization daemon: playlist digests are agent-driven |

## Tech Stack

- Python 3 stdlib only for scripts (no pip deps). Bash for the prerequisite scripts.
- External tools: `yt-dlp` and `ffmpeg` (required); `uv`/`uvx` (optional, for the Whisper fallback).
- The Whisper fallback uses `mlx-whisper` (Apple Silicon) or `openai-whisper`, both via `uvx`.

## Commands

```bash
S=skills/dm-summarize-video/scripts
$S/check-prerequisites.sh                          # exit 1 + hints if a required tool is missing
$S/install-prerequisites.sh [--upgrade]            # brew / apt install of missing tools
python3 $S/prepare_video.py <url> [-d] [--visual] [--lang xx] [--source auto|captions|whisper] [--refresh] [--cookies-from-browser B]
python3 $S/list_videos.py <playlist|channel url> [--limit 10]
python3 $S/extract_frames.py <video-dir> [--max 40] [--threshold 0.3]
python3 $S/save_summary.py <video-or-digest-dir> --mode summary [--summary-lang de] < body.md
cd $S && python3 -m unittest discover -p 'test_*.py'
python3 scripts/check-plugins.py
```

## Project Structure

```
skills/dm-summarize-video/
  SKILL.md                      non-deterministic workflow only
  templates/<mode>.md           output shape per mode
  scripts/
    _common.py                  paths, slugs, tool checks, yt-dlp base, timestamps, links
    prepare_video.py            metadata → folder → transcript (captions/Whisper) → [-d video] → [--visual frames]; prints JSON
    extract_frames.py           ffmpeg scene detection → frames/NNNN.jpg + index.md
    list_videos.py              playlist/channel → JSON video list + digest folder
    save_summary.py             stdin body → summary.md / digest.md with frontmatter
    check-prerequisites.sh
    install-prerequisites.sh
    test_*.py                   offline unit tests
```

Library layout:

```
~/me/summaries/videos/<platform>/<user>/<title-slug>/{summary.md, transcript.md, metadata.json, video.mp4, frames/}
~/me/summaries/videos/<platform>/<user>/_digests/<playlist-slug>/{digest.md, metadata.json}
```

`<user>` is the channel handle without `@` (`uploader_id`), falling back to the channel/uploader name, then `unknown`.
`<platform>` is the yt-dlp extractor key, lowercased (`youtube`, `tiktok`, `vimeo`, …).

## Code Style

Match the existing script: stdlib, type hints, small pure helpers above the side-effecting functions,
`log()` to stderr, and machine output on stdout (one JSON object for `prepare_video.py` / `list_videos.py`).

## Testing Strategy

- Offline unit tests for every pure helper: slugs, folder resolution and ID lookup, VTT parsing, track picking,
  paragraphs with links, showinfo parsing and frame sampling, frontmatter rendering, and playlist JSON parsing.
- A local end-to-end run on an mp4 served from localhost (generated with `say` + `ffmpeg`), covering the Whisper path,
  `-d`, `--visual` and `save_summary.py`, with `DM_SUMMARIZE_VIDEO_ROOT` pointed at a temp dir.
- A best-effort live YouTube run; it can hit rate limits, so it is not a gate.

## Boundaries

- Always: check tools before use; keep writes inside the resolved video folder; keep scripts stdlib-only.
- Ask first: deleting an existing summary folder; installing tools system-wide (the install script is explicit and user-run).
- Never: call paid APIs; write outside `DM_SUMMARIZE_VIDEO_ROOT` (except `uvx` model caches); edit `docs/shotfiles/`.

## Success Criteria

```yaml
criteria:
  - description: unit tests pass
    verify: cd skills/dm-summarize-video/scripts && python3 -m unittest discover -p 'test_*.py'
    expected_exit: 0
  - description: plugin manifests and skill rules consistent (incl. prerequisite scripts)
    verify: python3 scripts/check-plugins.py
    expected_exit: 0
  - description: prerequisite check passes on this machine
    verify: skills/dm-summarize-video/scripts/check-prerequisites.sh
    expected_exit: 0
  - description: Claude plugin still validates
    verify: claude plugin validate . --strict
    expected_exit: 0
  - description: CLAUDE.md and AGENTS.md document the script rules
    verify: grep -q 'check-prerequisites' CLAUDE.md && grep -q 'check-prerequisites' AGENTS.md
    expected_exit: 0
```

## Open Questions

None blocking. Resolved defaults: slug style is lowercase kebab (max 80 chars); the default mode is `summary`;
the frame cap is 40.

## Background

_See MIGRATION_NOTES.md._

## Approach

_See MIGRATION_NOTES.md._


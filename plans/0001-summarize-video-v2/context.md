---
name: summarize-video-v2-context
description: Files, patterns and gotchas for summarize-video-v2.
---

## Files to Load

- skills/dm-summarize-video/SKILL.md
- skills/dm-summarize-video/scripts/*.py
- scripts/check-plugins.py, .claude-plugin/plugin.json, .codex-plugin/plugin.json

## Patterns

- Scripts are stdlib-only Python with pure helpers + thin side-effect layer; JSON on stdout, logs on stderr.
- Every external tool goes through `_common.require()` before first use.

## Gotchas

- YouTube returns 429 on caption tracks when many languages are requested at once, or after bursts; request exactly one track.
- yt-dlp ages fast: an old version breaks downloads (seen 2026-09-25: 403 on audio until upgraded to 2026.08.19).
- `CLAUDE.md` / `AGENTS.md` are hal-managed; custom sections may need re-adding after a hal agent-file update.

## Links

- research/0002-summarize-video/result.md

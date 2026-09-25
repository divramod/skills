---
name: x-source
description: x.com: FxTwitter thread + replies always, quoted posts, community notes; post video → transcript + background download via the video source.
status: shipped
phase_id: "005"
depends_on: ["001"]
wave: "02"
created: 2026-09-25
tier: large
tier_source: manual
---

## Overview

Summarize a post or thread plus its reactions, including the transcript of any video in it.

## Architecture

`scripts/x/prepare.py <url>` gets `api.fxtwitter.com/2/thread/<id>` (author chain) and `/2/conversation/<id>` (replies, paginated with the cursor up to a cap), falling back to `cdn.syndication.twimg.com/tweet-result` for a single post. content.md has `## Thread` (permalink per post, quoted posts inline, media noted, community note) and `## Replies` (author, likes, permalink). If a post has video, it runs `scripts/video/prepare.py <post url>` (yt-dlp handles x.com): transcript into `## Video` and the download in the background as with videos (`--skip-download` opts out). Folder: `posts/x/<user>/<first-words>-<id>/`.

## Approach

Verify the FxTwitter v2 response shape live once and save it as a fixture. The replies cap defaults to 200 (flag `--max-replies`).

## Tasks

- [x] **T401** — FxTwitter client (thread, conversation w/ cursor, syndication fallback)
  **Acceptance**: fixture tests; fallback logged
  **Verify**: `cd skills/tell-me/scripts && for d in */; do python3 -m unittest discover -s "$d" -p 'test_*.py' || exit 1; done`
  **Files**: skills/tell-me/scripts/x/client.py
  **Size**: M
  **State**:
  - [x] built
  - [x] tested
  - [x] reviewed
  - [x] shipped

- [x] **T402** — `x/prepare.py` content.md (thread, quotes, notes, replies) + metadata extras (views, likes, reposts)
  **Acceptance**: fixture renders
  **Verify**: `cd skills/tell-me/scripts && for d in */; do python3 -m unittest discover -s "$d" -p 'test_*.py' || exit 1; done`
  **Files**: skills/tell-me/scripts/x/prepare.py
  **Size**: M
  **State**:
  - [x] built
  - [x] tested
  - [x] reviewed
  - [x] shipped

- [x] **T403** — Video part: call video prepare, merge transcript, background download
  **Acceptance**: a fixture post with video triggers `video/prepare.py <post url> --dir <x folder> --content-part video` (new flags: write into the given folder, keep the transcript as `video-transcript.md` and don't create a second `videos/…` library entry); mocked in the test
  **Verify**: `cd skills/tell-me/scripts && for d in */; do python3 -m unittest discover -s "$d" -p 'test_*.py' || exit 1; done`
  **Files**: skills/tell-me/scripts/x/prepare.py
  **Size**: S
  **State**:
  - [x] built
  - [x] tested
  - [x] reviewed
  - [x] shipped

- [x] **T404** — prereq scripts (video tools optional) + SUBSKILL.md (thread vs reactions, reactions via discussion.md) + template.md
  **Acceptance**: check-plugins passes
  **Verify**: review
  **Files**: skills/tell-me/scripts/x/*.sh, subskills/x/, templates/x/
  **Size**: S
  **State**:
  - [x] built
  - [x] tested
  - [x] reviewed
  - [x] shipped

- [x] **T405** — E2E: a text thread and a post with video
  **Acceptance**: library pages; video downloads in the background
  **Verify**: manual
  **Files**: –
  **Size**: S
  **State**:
  - [x] built
  - [x] tested
  - [x] reviewed
  - [x] shipped

## Risks

FxTwitter is unofficial and can break or rate-limit; protected accounts are unreachable (clear error).

## Open Questions

None.

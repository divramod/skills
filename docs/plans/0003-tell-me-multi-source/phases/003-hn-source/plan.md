---
name: hn-source
description: Hacker News: Algolia comment tree, linked article via the web extractor, discussion as themes with attributed quotes, check_quotes.py, past discussions.
status: in_progress
phase_id: "003"
depends_on: ["001", "002"]
wave: "03"
created: 2026-09-25
tier: large
tier_source: manual
---

## Overview

One HN item → one folder. The summary has 'The article' followed by 'The discussion'.

## Architecture

`scripts/hn/prepare.py <item url|id>` fetches `hn.algolia.com/api/v1/items/<id>` (Firebase fallback), flattens the tree into `## Discussion` with `- **author** [→](https://news.ycombinator.com/item?id=<cid>) (depth n, reply to <parent>): text` (HTML unescaped), and gets the story `url` through `web/extract.py` (imported via `sys.path` to `scripts/web`; source→source import is allowed, shared→source is not) into `## Article`. Ask/Show HN posts have no article. `hn/related.py` finds past discussions of the same URL: Algolia `search?query=<url>&restrictSearchableAttributes=url`. `shared/check_quotes.py <dir>` (body on stdin) reports quotes that are not found in content.md, ignoring whitespace and HTML entities. Folder: `discussions/hn/<title>-<id>/`.

## Approach

Fixtures: one small thread and one big thread (≥300 comments), both Algolia JSON. For large threads, content.md stays whole; the SUBSKILL tells the agent to work through it top-level thread by top-level thread.

## Tasks

- [ ] **T201** — `hn/prepare.py`: Algolia fetch + Firebase fallback, flatten with attribution/permalinks, article via web extractor
  **Acceptance**: the fixture renders the expected content.md; a deleted/dead comment is skipped
  **Verify**: `cd skills/tell-me/scripts && for d in */; do python3 -m unittest discover -s "$d" -p 'test_*.py' || exit 1; done`
  **Files**: skills/tell-me/scripts/hn/
  **Size**: M
  **State**:
  - [x] built
  - [x] tested
  - [ ] reviewed
  - [ ] shipped

- [ ] **T202** — `shared/check_quotes.py` + test
  **Acceptance**: an invented quote is flagged, a real quote passes (normalized)
  **Verify**: `cd skills/tell-me/scripts && for d in */; do python3 -m unittest discover -s "$d" -p 'test_*.py' || exit 1; done`
  **Files**: skills/tell-me/scripts/shared/check_quotes.py, test_check_quotes.py
  **Size**: S
  **State**:
  - [x] built
  - [x] tested
  - [ ] reviewed
  - [ ] shipped

- [ ] **T203** — `hn/related.py` past discussions (same URL, other ids)
  **Acceptance**: fixture test
  **Verify**: `cd skills/tell-me/scripts && for d in */; do python3 -m unittest discover -s "$d" -p 'test_*.py' || exit 1; done`
  **Files**: skills/tell-me/scripts/hn/related.py
  **Size**: S
  **State**:
  - [x] built
  - [x] tested
  - [ ] reviewed
  - [ ] shipped

- [ ] **T204** — `subskills/shared/discussion.md` (Willison method: themes as headers, attributed quotes, uncommon opinions, run check_quotes) + `subskills/hn/SUBSKILL.md` + `templates/hn/template.md`
  **Acceptance**: linked from SKILL.md
  **Verify**: review
  **Files**: skills/tell-me/subskills/, skills/tell-me/templates/hn/
  **Size**: S
  **State**:
  - [x] built
  - [x] tested
  - [ ] reviewed
  - [ ] shipped

- [ ] **T205** — hn prereq scripts (python3 only) + E2E on one link post and one Ask HN
  **Acceptance**: summary.html in library
  **Verify**: manual
  **Files**: skills/tell-me/scripts/hn/*.sh
  **Size**: S
  **State**:
  - [x] built
  - [x] tested
  - [ ] reviewed
  - [ ] shipped

## Risks

Algolia lags minutes behind for brand-new items (Firebase fallback); very large threads (>1000 comments) are expensive in tokens.

## Open Questions

None.

# UAT — tell-me-multi-source

Masterplan for tell-me multi-source — restructure into subskills/scripts/templates with shared/, then add web, hn, github, x, file sources, multiple inputs and the library source filter.

- Status: shipped
- Shipped: 2026-09-25
- Tier: large
- Phases: 8
- Tasks: 42
- Tokens spent: 0

## Phases

### 001-restructure-and-contract — restructure-and-contract
Status: shipped · Tasks: 9

Move tell-me to subskills/scripts/templates with shared/, add the router + source contract + per-folder prereqs; video only, no regressions.

### 002-web-source — web-source
Status: shipped · Tasks: 5

Blog posts / web articles: trafilatura + defuddle in parallel, best result wins; Jina Reader then Wayback fallback; paragraph anchors.

### 003-hn-source — hn-source
Status: shipped · Tasks: 5

Hacker News: Algolia comment tree, linked article via the web extractor, discussion as themes with attributed quotes, check_quotes.py, past discussions.

### 004-github-source — github-source
Status: shipped · Tasks: 7

GitHub repos via API/gh (+README, languages, release, tree, docs), --deep via repomix, issues/PRs/discussions in discussion shape, similar repos.

### 005-x-source — x-source
Status: shipped · Tasks: 5

x.com: FxTwitter thread + replies always, quoted posts, community notes; post video → transcript + background download via the video source.

### 006-file-source — file-source
Status: shipped · Tasks: 4

Local documents: markitdown → pdftotext/pandoc fallback, original copied, page anchors, sha256 dedupe.

### 007-multi-input-digest — multi-input-digest
Status: shipped · Tasks: 3

Multiple inputs in one call and a generalized digest across any sources.

### 008-library-ui-and-docs — library-ui-and-docs
Status: shipped · Tasks: 4

Library sidebar source filter + icons, per-source header panels, README/plugin metadata, final e2e.


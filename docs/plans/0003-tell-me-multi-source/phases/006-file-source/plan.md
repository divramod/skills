---
name: file-source
description: Local documents: markitdown → pdftotext/pandoc fallback, original copied, page anchors, sha256 dedupe.
status: approved
phase_id: "006"
depends_on: ["001"]
wave: "02"
created: 2026-09-25
tier: large
tier_source: manual
---

## Overview

Summarize a local pdf/docx/pptx/xlsx/epub/html/md/txt file.

## Architecture

`scripts/file/prepare.py <path>` hashes the file (sha256 = id; dedupe), copies it to `<dir>/original.<ext>`, converts it with `uvx --from 'markitdown[all]' markitdown <file>` (md/txt are read directly; fallback `pdftotext -layout` per page, `pandoc` for docx/epub). For PDFs, a page split gives `[p. n](original.pdf#page=n)` anchors. Metadata: title from the doc properties or first heading, author, pages, word count. Folder: `documents/<parent-folder>/<stem>/`. The page links to `original.<ext>`.

## Approach

Fixtures: a 3-page PDF, a docx and an md file, generated in the tests where possible.

## Tasks

- [ ] **T501** — Converter chain + page splitting + title/author extraction
  **Acceptance**: fixture tests per type; fallback path tested with markitdown mocked missing
  **Verify**: `cd skills/tell-me/scripts && for d in */; do python3 -m unittest discover -s "$d" -p 'test_*.py' || exit 1; done`
  **Files**: skills/tell-me/scripts/file/convert.py
  **Size**: M
  **State**:
  - [x] built
  - [x] tested
  - [ ] reviewed
  - [ ] shipped

- [ ] **T502** — `file/prepare.py`: copy, hash dedupe, content.md with page anchors, metadata
  **Acceptance**: re-run of the same file reuses the folder; a changed file → new version note
  **Verify**: `cd skills/tell-me/scripts && for d in */; do python3 -m unittest discover -s "$d" -p 'test_*.py' || exit 1; done`
  **Files**: skills/tell-me/scripts/file/prepare.py
  **Size**: M
  **State**:
  - [x] built
  - [x] tested
  - [ ] reviewed
  - [ ] shipped

- [ ] **T503** — prereq scripts (uvx required; pdftotext, pandoc optional) + SUBSKILL.md + template.md
  **Acceptance**: check-plugins passes
  **Verify**: review
  **Files**: skills/tell-me/scripts/file/*.sh, subskills/file/, templates/file/
  **Size**: S
  **State**:
  - [x] built
  - [x] tested
  - [ ] reviewed
  - [ ] shipped

- [ ] **T504** — E2E: a real PDF paper and a docx
  **Acceptance**: library pages, page links open the PDF at the page
  **Verify**: manual
  **Files**: –
  **Size**: S
  **State**:
  - [x] built
  - [x] tested
  - [ ] reviewed
  - [ ] shipped

## Risks

markitdown is weak on multi-column PDFs and tables (docling is the future opt-in); large files (size warning > 50 MB).

## Open Questions

None.

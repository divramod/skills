---
name: web-source
description: Blog posts / web articles: trafilatura + defuddle in parallel, best result wins; Jina Reader then Wayback fallback; paragraph anchors.
status: shipped
phase_id: "002"
depends_on: ["001"]
wave: "02"
created: 2026-09-25
tier: large
tier_source: manual
---

## Overview

Summarize any web article with the highest-quality extraction available.

## Architecture

`scripts/web/prepare.py <url>` runs `uvx trafilatura --markdown --with-metadata -u <url>` and `npx -y defuddle parse <url> --markdown --json` in parallel, scores each result (main-content words minus boilerplate markers), keeps the better text and merges the metadata (defuddle/schema.org first). If the result is under 200 words, it tries `https://r.jina.ai/<url>`, then the Wayback snapshot from `archive.org/wayback/available`. `content.md` has a `[¶n](<url>#:~:text=<first 5 words>)` anchor per paragraph and the heading `#id`s when the page has them. Folder: `articles/<site>/<title-slug>/`; id = canonical URL.

## Approach

Verify the CLI flags against the installed tools (`uvx trafilatura --help`, `npx defuddle --help`) before coding. Record fixtures for three pages: a normal blog post, a JS-heavy page, and a dead page.

## Tasks

- [x] **T101** — Extractor wrappers + scorer + merge (trafilatura, defuddle, Jina, Wayback), each with a timeout and a clear error
  **Acceptance**: fixture tests pick the expected winner; the fallback order is logged
  **Verify**: `cd skills/tell-me/scripts && for d in */; do python3 -m unittest discover -s "$d" -p 'test_*.py' || exit 1; done`
  **Files**: skills/tell-me/scripts/web/extract.py, test_extract.py, fixtures/
  **Size**: M
  **State**:
  - [x] built
  - [x] tested
  - [x] reviewed
  - [x] shipped

- [x] **T102** — `web/prepare.py`: content.md with paragraph text-fragment anchors, metadata contract, dedupe by canonical URL
  **Acceptance**: the anchor test (URL-encoding, uniqueness) passes; a re-run reuses the folder
  **Verify**: `cd skills/tell-me/scripts && for d in */; do python3 -m unittest discover -s "$d" -p 'test_*.py' || exit 1; done`
  **Files**: skills/tell-me/scripts/web/prepare.py, test_prepare.py
  **Size**: M
  **State**:
  - [x] built
  - [x] tested
  - [x] reviewed
  - [x] shipped

- [x] **T103** — `web/check-/install-prerequisites.sh` (uvx, npx/node)
  **Acceptance**: check-plugins passes
  **Verify**: `python3 scripts/check-plugins.py`
  **Files**: skills/tell-me/scripts/web/*.sh
  **Size**: XS
  **State**:
  - [x] built
  - [x] tested
  - [x] reviewed
  - [x] shipped

- [x] **T104** — `subskills/web/SUBSKILL.md` (article vs listicle vs docs page, paywall note, garbled extraction note) + `templates/web/template.md` (argument, evidence, counterpoints, Related reading via web search)
  **Acceptance**: SUBSKILL < 150 lines
  **Verify**: review
  **Files**: skills/tell-me/subskills/web/, skills/tell-me/templates/web/
  **Size**: S
  **State**:
  - [x] built
  - [x] tested
  - [x] reviewed
  - [x] shipped

- [x] **T105** — E2E: 2 real blog posts (one JS-heavy)
  **Acceptance**: summary.html in library, links dated
  **Verify**: manual
  **Files**: –
  **Size**: S
  **State**:
  - [x] built
  - [x] tested
  - [x] reviewed
  - [x] shipped

## Risks

defuddle calls itself a work in progress; Jina rate limit (20/min); text fragments are not supported in Firefox before v131 (links still open the page).

## Open Questions

None.

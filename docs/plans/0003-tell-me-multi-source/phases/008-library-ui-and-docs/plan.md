---
name: library-ui-and-docs
description: Library sidebar source filter + icons, per-source header panels, README/plugin metadata, final e2e.
status: shipped
schema_version: 1
phase_id: '008'
depends_on:
- '002'
- '003'
- '004'
- '005'
- '006'
- '007'
wave: 4
created: '2026-09-25'
tier: large
tier_source: manual
---

## Overview

Make the mixed library pleasant to use and document the new skill.

## Architecture

`library.py` entries get `source`; the sidebar gets a source filter (chips) and an icon per source, and keeps the existing sort options. The `render_html` header panels: web (site, reading time), github (stars, license, release, languages), x (author, engagement, community note), hn (points, comments, article link), file (pages, 'open original'). README, plugin.json description/keywords, and a version bump.

## Approach

Build the panels on the dispatch hook from 001; each panel is small and reads only `metadata.extras`.

## Tasks

- [x] **T701** — Sidebar source filter + icons
  **Acceptance**: test_library covers the filter data; manual check in the browser
  **Verify**: `cd skills/tell-me/scripts && for d in */; do python3 -m unittest discover -s "$d" -p 'test_*.py' || exit 1; done`
  **Files**: skills/tell-me/scripts/shared/library.py
  **Size**: M
  **State**:
  - [x] built
  - [x] tested
  - [x] reviewed
  - [x] shipped

- [x] **T702** — Header panels per source
  **Acceptance**: test_render_html renders each panel from fixture metadata
  **Verify**: `cd skills/tell-me/scripts && for d in */; do python3 -m unittest discover -s "$d" -p 'test_*.py' || exit 1; done`
  **Files**: skills/tell-me/scripts/shared/render_html.py
  **Size**: M
  **State**:
  - [x] built
  - [x] tested
  - [x] reviewed
  - [x] shipped

- [x] **T703** — README + plugin.json/.codex-plugin description/keywords + version bump
  **Acceptance**: check-plugins passes
  **Verify**: `python3 scripts/check-plugins.py`
  **Files**: README.md, .claude-plugin/*, .codex-plugin/*
  **Size**: S
  **State**:
  - [x] built
  - [x] tested
  - [x] reviewed
  - [x] shipped

- [x] **T704** — Final e2e: one input per source + `verify-success.sh`
  **Acceptance**: all criteria pass
  **Verify**: `hal plan spec render-verify` + run
  **Files**: –
  **Size**: S
  **State**:
  - [x] built
  - [x] tested
  - [x] reviewed
  - [x] shipped

## Risks

Sidebar JS grows. Keep it dependency-free.

## Open Questions

None.


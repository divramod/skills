---
name: github-source
description: GitHub repos via API/gh (+README, languages, release, tree, docs), --deep via repomix, issues/PRs/discussions in discussion shape, similar repos.
status: approved
phase_id: "004"
depends_on: ["001"]
wave: "02"
created: 2026-09-25
tier: large
tier_source: manual
---

## Overview

Summarize a repo (what, why, how to use, architecture) or an issue/PR/discussion thread.

## Architecture

`scripts/github/prepare.py <url> [--deep]`. It uses `gh api` when gh is installed and authenticated, otherwise urllib REST (60 req/h, and says so). Repo content: `/repos/{o}/{r}`, `/readme`, `/languages`, `/releases/latest`, `/topics`, the tree (`/git/trees/<branch>?recursive=1`, top 200 paths) and `docs/*.md`/`*.md` at the root up to a byte budget. Anchors: `blob/<sha>/<path>#L<n>`. `--deep`: `npx -y repomix --remote <url> --style markdown --compress -o <dir>/repo-pack.md`. Issues/PRs: body + comments (+ review comments for PRs) in discussion shape; discussions via `gh api graphql`. `github/related.py`: `gh search repos <topics/keywords> --json` for similar repos. Folder: `repos/github/<owner>/<repo>/`, issues under `repos/github/<owner>/<repo>/issues/<n>-<slug>/`.

## Approach

Probe `gh api` and `npx repomix --help` first. Put the API JSON fixtures in `fixtures/`.

## Tasks

- [ ] **T301** — gh-or-REST client with rate-limit messaging
  **Acceptance**: fixture tests for both paths
  **Verify**: `cd skills/tell-me/scripts && for d in */; do python3 -m unittest discover -s "$d" -p 'test_*.py' || exit 1; done`
  **Files**: skills/tell-me/scripts/github/client.py
  **Size**: S
  **State**:
  - [x] built
  - [x] tested
  - [ ] reviewed
  - [ ] shipped

- [ ] **T302** — repo `prepare.py`: metadata extras (stars, license, release, pushed_at, languages), README + docs + tree into content.md with anchors
  **Acceptance**: fixture renders; re-run reuses the folder
  **Verify**: `cd skills/tell-me/scripts && for d in */; do python3 -m unittest discover -s "$d" -p 'test_*.py' || exit 1; done`
  **Files**: skills/tell-me/scripts/github/prepare.py
  **Size**: M
  **State**:
  - [x] built
  - [x] tested
  - [ ] reviewed
  - [ ] shipped

- [ ] **T303** — `--deep` via repomix (optional tool check, size warning)
  **Acceptance**: missing npx → exit 2 with hint
  **Verify**: `cd skills/tell-me/scripts && for d in */; do python3 -m unittest discover -s "$d" -p 'test_*.py' || exit 1; done`
  **Files**: skills/tell-me/scripts/github/prepare.py
  **Size**: S
  **State**:
  - [x] built
  - [x] tested
  - [ ] reviewed
  - [ ] shipped

- [ ] **T304** — issues / PRs / discussions → discussion-shaped content.md
  **Acceptance**: fixture tests per kind
  **Verify**: `cd skills/tell-me/scripts && for d in */; do python3 -m unittest discover -s "$d" -p 'test_*.py' || exit 1; done`
  **Files**: skills/tell-me/scripts/github/thread.py
  **Size**: M
  **State**:
  - [x] built
  - [x] tested
  - [ ] reviewed
  - [ ] shipped

- [ ] **T305** — `github/related.py` similar repos
  **Acceptance**: fixture test
  **Verify**: `cd skills/tell-me/scripts && for d in */; do python3 -m unittest discover -s "$d" -p 'test_*.py' || exit 1; done`
  **Files**: skills/tell-me/scripts/github/related.py
  **Size**: S
  **State**:
  - [x] built
  - [x] tested
  - [ ] reviewed
  - [ ] shipped

- [ ] **T306** — prereq scripts (gh optional, npx optional) + SUBSKILL.md + template.md (repo & thread shapes)
  **Acceptance**: check-plugins passes
  **Verify**: review
  **Files**: skills/tell-me/scripts/github/*.sh, subskills/github/, templates/github/
  **Size**: S
  **State**:
  - [x] built
  - [x] tested
  - [ ] reviewed
  - [ ] shipped

- [ ] **T307** — E2E: one repo, one repo with --deep, one issue, one PR
  **Acceptance**: library pages
  **Verify**: manual
  **Files**: –
  **Size**: S
  **State**:
  - [x] built
  - [x] tested
  - [ ] reviewed
  - [ ] shipped

## Risks

Unauthenticated rate limit; big monorepos (budget + --deep warning); GraphQL is needed for discussions (gh only).

## Open Questions

None.

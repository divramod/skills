---
name: tell-me-multi-source
description: 'Generalize tell-me from videos to blog posts, GitHub repos, X posts, Hacker News threads and local documents via a router SKILL.md + per-source subskills, scripts and templates with shared/ folders'
status: approved
approved: '2026-09-25'
schema_version: 1
created: '2026-09-25'
tier: large
tier_source: manual
---

## Objective

`tell-me <anything>` summarizes whatever it is given, not just videos: a blog post, a GitHub repo, an x.com post or
thread, a Hacker News post (article + discussion), or a document on the local filesystem. Each source gets the
same treatment the videos get today: a folder in the library with `summary.md`, `summary.html`, the extracted
content, `metadata.json`, the links section with dates, and an entry in the library sidebar.

Shot 9 of `docs/shotfiles/main.md`. Research: `docs/research/0003-tell-me-multi-source/result.md`.

## Goals

- **G1 (must)** — Route any input to a source. The skill SHALL classify a URL or path into exactly one of
  `video | web | github | x | hn | file` with a deterministic script, falling back to `web` for unknown `http(s)`
  URLs and to `video` for anything yt-dlp supports.
- **G2 (must)** — One contract for every source. Every `scripts/<source>/prepare.py` SHALL write the same folder
  shape (`metadata.json` with the shared fields, a content markdown file with citable anchor links) and print the
  same JSON envelope, so the shared steps (`save_summary`, `render_html`, `library`, `check_links`) need no
  per-source branches beyond an optional header panel.
- **G3 (must)** — Split by source. The skill SHALL be laid out as `SKILL.md` (router + shared steps) +
  `subskills/{shared,<source>}/`, `scripts/{shared,<source>}/`, `templates/{shared,<source>}/`, and SKILL.md SHALL
  link each subskill file directly (one level deep).
- **G4 (must)** — No regression for videos. Existing video summaries SHALL keep their paths, open in the library,
  and every existing test SHALL pass after the move.
- **G5 (must)** — Per-source prerequisites. Each `scripts/<source>/` that calls external tools SHALL ship an
  executable `check-prerequisites.sh` + `install-prerequisites.sh`; a missing tool SHALL exit 2 naming that
  source's install script; `scripts/check-plugins.py` SHALL enforce this per folder.
- **G6 (must)** — Discussions as themes with quotes. HN threads and X replies SHALL be summarized as themes with
  attributed verbatim quotes, and a script SHALL flag quotes that don't occur in the content file.
- **G7 (must)** — Source-specific "next" section. Every source SHALL end with a related-items list from a script
  (similar videos / similar repos via `gh search repos` / past HN discussions of the same URL via Algolia), or from
  web search where no script exists.
- **G8 (must)** — X posts with video: the video source SHALL run automatically for the post's video (transcript
  + best-quality download in the background, `--skip-download` opts out) and its transcript SHALL become a
  "Video" part of `content.md`.
- **G9 (should)** — GitHub depth: default API + README + tree + `docs/*.md`; `--deep` SHALL pack the whole repo
  with `npx repomix --remote <url> --compress`.
- **G10 (should)** — Multiple inputs: `tell-me <a> <b> …` SHALL summarize each input and offer a digest across
  them (the playlist digest, generalized).
- **G11 (should)** — GitHub issues, pull requests and discussions (`github.com/o/r/{issues,pull,discussions}/N`)
  SHALL route to `github` in discussion shape (body + comments as themes with quotes).

## Non-Goals

- **G-N1** — No login-walled or paid APIs (X API, paywalled sites); cookies only where yt-dlp already supports them.
- **G-N2** — No new summary modes; the six modes stay and become source-neutral.
- **G-N3** — No automatic recursion beyond one hop (HN → linked article is the only built-in hop).
- **G-N4** — Not renaming the skill; it stays `tell-me`.
- **G-N5** — Reddit, podcasts-as-RSS, email, Slack: later sources, but the contract must make them a drop-in.

## Tech Stack

- Python 3 stdlib for all scripts (as today); network via `urllib`.
- External tools per source:

| Source | Required | Optional / fallback |
|---|---|---|
| shared | python3 | gh (link dates) |
| video | yt-dlp, ffmpeg, ffprobe | uvx (Whisper) |
| web | uvx (trafilatura), npx (defuddle) | — (Jina Reader + Wayback via urllib) |
| github | — (REST via urllib, 60 req/h) | gh (auth, 5000 req/h, `gh search repos`, GraphQL for discussions), npx (repomix for `--deep`) |
| x | — (FxTwitter v2 via urllib) | video-source tools (yt-dlp, ffmpeg) for posts with video |
| hn | — (Algolia via urllib) | — (Firebase fallback via urllib) |
| file | uvx (runs `markitdown[all]`) | pdftotext (poppler), pandoc |

## Commands

```bash
S=<skill-dir>/scripts
python3 $S/shared/prepare.py "<url-or-path>" [...] [source flags]  # one or more inputs; routes, runs scripts/<source>/prepare.py, prints the envelope
python3 $S/shared/route.py "<url-or-path>"                   # {"source": "github", "id": "owner/repo", ...}
python3 $S/shared/save_summary.py "<dir>" --mode <mode> --summary-lang xx --model <id> --open <<'EOF' ... EOF
python3 $S/shared/check_quotes.py "<dir>" <<'EOF' ... EOF    # G6: quotes missing from the content file
python3 $S/<source>/related.py "<dir>" [--query ...]         # G7 (video: today's similar_videos.py)
$S/<source>/install-prerequisites.sh                        # on exit code 2
cd $S && python3 -m unittest discover -s . -p 'test_*.py' -t .
python3 scripts/check-plugins.py
```

## Project Structure

```
skills/tell-me/
  SKILL.md                     # router: no-link → open last; prepare; read subskills/<source>/SUBSKILL.md; mode; write; links; save
  subskills/
    shared/
      links.md                 # link lookup rules (books, wikipedia, repos, dates, broken links) — moved out of SKILL.md
      discussion.md            # themes-with-quotes method (HN, X replies)
    video/SUBSKILL.md          # --visual, --skip-download, Whisper, bot checks, playlists/channels + digest
    web/SUBSKILL.md            # article vs listicle vs docs page; paywall/fallback notes
    github/SUBSKILL.md         # repo: what / why / how to use / architecture; --deep; issues/PRs/discussions
    x/SUBSKILL.md              # thread + replies (reactions as themes); quoted posts; video part
    hn/SUBSKILL.md             # article first, then discussion; Ask/Show HN without article
    file/SUBSKILL.md           # pdf/docx/pptx/epub/md; page anchors; long documents chapter by chapter
  scripts/
    shared/                    # _common.py, route.py, prepare.py, save_summary.py, render_html.py, library.py,
                               # serve_library.py, check_links.py, link_dates.py, check_quotes.py,
                               # check-prerequisites.sh, install-prerequisites.sh, test_*.py
    video/                     # prepare.py (was prepare_video.py), download_video.py, extract_frames.py,
                               # list_videos.py, related.py (was similar_videos.py), prereq scripts, tests
    web/  github/  x/  hn/  file/   # prepare.py [+ related.py] + prereq scripts + tests
  templates/
    shared/                    # summary.md tldr.md detailed.md wisdom.md qa.md digest.md links.md (source-neutral)
    video/template.md          # chapters mode + "Similar videos"
    web/template.md  github/template.md  x/template.md  hn/template.md  file/template.md
```

### Library layout

Root `~/me/summaries` (`TELL_ME_ROOT`; `DM_SUMMARIZE_VIDEO_ROOT` still honoured, pointing at the `videos` subtree).
Existing video folders don't move:

| Source | Folder |
|---|---|
| video | `videos/<platform>/<channel>/<title>/` (unchanged) |
| web | `articles/<site>/<title>/` |
| github | `repos/github/<owner>/<repo>/` |
| x | `posts/x/<user>/<first-words>-<id>/` |
| hn | `discussions/hn/<title>-<id>/` |
| file | `documents/<parent-folder>/<file-stem>/` |

`library.js` moves to `<root>/library.js`; the sidebar gets a source filter and a per-source icon.

### Contract (G2)

`metadata.json` shared fields: `source`, `id` (dedupe key), `url` (canonical; `file://` for local), `title`,
`author`, `published`, `fetched`, `site`, `word_count`, `duration` (video), `extractor`, `content_file`,
`extras{}` (per source: stars/license/release, points/comment count, views/likes/community note, pages, …).
Video keeps its current keys and gains `source: video`.

Content file: `content.md` for every source, video included. A one-off `scripts/video/migrate_library.py` renames
existing `transcript.md` → `content.md`, updates `metadata.json` and re-renders the pages (idempotent, dry-run
default). Every content file carries **anchor links the agent copies, never builds**:

| Source | Anchor |
|---|---|
| video | timestamp links (today) |
| web | per paragraph `[¶n](<url>#:~:text=<first words>)` (text fragments) or the heading's `#id` |
| github | `blob/<sha>/<path>#L<n>` for files, README heading anchors |
| x | permalink per post |
| hn | `news.ycombinator.com/item?id=<comment id>` per comment, with author + depth |
| file | `[p. n](file://<path>#page=n)` for PDFs, heading anchors otherwise |

Envelope printed by `prepare.py`: `{source, dir, summary_exists, subskill, template, content_file, …source extras}`
so the agent reads exactly `subskill` and `template` next.

## Code Style

Match the existing scripts: stdlib Python, `argparse` with `__doc__`, `run_main()` exit codes (1 expected
error, 2 missing tool), JSON on stdout, progress on stderr via `log()`, atomic `write_json`. Shared imports via
`scripts/shared/_common.py` (source scripts add `scripts/shared` to `sys.path` in one line). Subskill files:
short imperative prose, no duplication of what SKILL.md or `subskills/shared/` already says.

## Testing Strategy

- `migrate_library.py` test on a temp library: transcript.md → content.md, second run is a no-op.
- Move every existing `test_*.py` with its script; all must stay green (G4).
- Unit tests per source with recorded fixtures (no network in tests): Algolia item JSON, FxTwitter status/thread
  JSON, GitHub repo/readme JSON, a trafilatura markdown sample, a small PDF/docx for `file`.
- `route.py` table test: ≥25 inputs (youtu.be, youtube shorts, vimeo, x.com/twitter.com/fixupx, HN item, github
  repo/tree/blob/issue, arbitrary blog, `~/doc.pdf`, relative path, `file://`).
- `check_quotes.py` test: invented quote flagged, real quote passes (whitespace/entity-insensitive).
- `check-plugins.py` test: a source folder with `subprocess` but without prereq scripts fails.
- Manual end-to-end: one real input per source, page opens in the library.

## Boundaries

- **Always:** keep deterministic work in scripts; keep SKILL.md < 500 lines and each SUBSKILL.md < 150; copy
  anchor links from the content file; one commit per phase.
- **Ask first:** adding a required tool to a source; changing the video folder layout; network in tests.
- **Never:** nested files named `SKILL.md`/`skill.md`; paid/login APIs; edit `docs/shotfiles/main.md`.

## Success Criteria

```yaml
criteria:
  - description: all tell-me tests pass (existing + new)
    verify: cd skills/tell-me/scripts && python3 -m unittest discover -s . -p 'test_*.py' -t .
    expected_exit: 0
  - description: plugin manifests + per-source prereq scripts are consistent
    verify: python3 scripts/check-plugins.py
    expected_exit: 0
  - description: router classifies every source
    verify: cd skills/tell-me/scripts && for u in https://youtu.be/dQw4w9WgXcQ https://github.com/yt-dlp/yt-dlp https://x.com/jack/status/20 https://news.ycombinator.com/item?id=1 https://example.com/blog/post ./README.md; do python3 shared/route.py "$u" || exit 1; done
    expected_exit: 0
  - description: every source has a subskill, a template and is linked from SKILL.md
    verify: cd skills/tell-me && for s in video web github x hn file; do test -f subskills/$s/SUBSKILL.md && test -f templates/$s/template.md && grep -q "subskills/$s/SUBSKILL.md" SKILL.md || exit 1; done
    expected_exit: 0
  - description: no transcript.md left in new-layout scripts (content.md everywhere)
    verify: "! grep -rn 'transcript.md' skills/tell-me/scripts --include='*.py' | grep -v migrate_library | grep -v test_"
    expected_exit: 0
  - description: no nested skill files
    verify: test -z "$(find skills/tell-me -mindepth 2 -iname skill.md)"
    expected_exit: 0
  - description: SKILL.md stays under 500 lines
    verify: test "$(wc -l < skills/tell-me/SKILL.md)" -lt 500
    expected_exit: 0
```

## Decisions (grill 2026-09-25, see grill.md)

- Subskill file: `subskills/<source>/SUBSKILL.md`; shared material in `subskills/shared/*.md`.
- Prereqs: per-source `check-/install-prerequisites.sh` in every `scripts/<source>/` (shared too) + top-level
  aggregators `scripts/check-prerequisites.sh` / `install-prerequisites.sh [--source x]`; `check-plugins.py` and
  the CLAUDE.md/AGENTS.md rule change to per-folder.
- Library: `~/me/summaries/<kind>/…`, videos unchanged, one `library.js` at the root.
- HN: one folder, `content.md` with the article and discussion parts; summary = "The article" + "The discussion".
- X: thread + replies always (FxTwitter `/2/thread` + `/2/conversation`); post video → transcript + background
  download automatically.
- GitHub: API + README by default, `--deep` = repomix.
- Local files: copied into the folder as `original.<ext>`, deduped by sha256.
- Web: highest quality — trafilatura and defuddle both run, the one with more main-content words wins, metadata
  merged (defuddle's schema.org preferred); < 200 words → Jina Reader (JS render) → Wayback.
- Content file: `content.md` everywhere, with a migration for the existing video library.
- Phases: P1 restructure + router + contract (video only, no regressions, content.md migration) · P2 web ·
  P3 hn (+ check_quotes) · P4 github (repos, issues/PRs/discussions, related repos) · P5 x (+ video part) ·
  P6 file · P7 multi-input + digest · P8 library sidebar source filter + README/docs.
- Scope additions: check_quotes.py, related items per source, multiple inputs, GitHub issues/PRs/discussions.

## Open Questions

None.

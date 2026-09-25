---
name: tell-me
description: Summarize anything from a URL or a path into a markdown note and an HTML page in ~/me/summaries — a video, playlist or channel (YouTube, TikTok, X, Vimeo, podcasts, any yt-dlp site), a blog post or web page, a GitHub repo, issue, pull request or discussion, an X post or thread with its replies, a Hacker News thread (article + discussion), or a local document (PDF, DOCX, PPTX, EPUB, Markdown). Several inputs at once get a digest across them. Each summary has anchor links back into the source, a links section (books, Wikipedia terms, repos, further reading, each with its date) and related items; modes tldr/summary/detailed/wisdom/qa (+ chapters for videos). Use when the user pastes a link or a file path and wants a summary, the gist, notes, or answers about it; called without input it opens the last summary in the browser.
---

# tell-me

Scripts do all deterministic work: routing, fetching, folders, downloads, anchor links, file writing and link
dates. Your job is the judgment: pick the mode, read, write the summary, and check it against the content.
`S=<skill-dir>/scripts`. Every script prints what it did; JSON goes to stdout and progress to stderr.

## 0. No input given

Open the most recent summary and stop:

```bash
python3 $S/shared/library.py --open-last
```

Tell the user what opened (the printed path) and its URL. If there are no summaries yet, ask for a link or a path.

## 1. Prepare

```bash
python3 $S/shared/prepare.py "<url-or-path>" [source flags]
```

It routes the input to exactly one source, runs `scripts/<source>/prepare.py`, and prints the envelope:
`source`, `kind`, `dir` (the library folder), `content_file`, `summary_exists`, `subskill`, `template`, plus the
source's own fields. Flags after the input go to the source script; the subskill lists them.

| Source | Input | Subskill |
|---|---|---|
| video | YouTube (video, playlist, channel), youtu.be, Vimeo, TikTok, podcasts, any yt-dlp site | [subskills/video/SUBSKILL.md](subskills/video/SUBSKILL.md) |
| web | any other http(s) page: blog posts, articles, docs | [subskills/web/SUBSKILL.md](subskills/web/SUBSKILL.md) |
| github | `github.com/<owner>/<repo>`, its `/issues/N`, `/pull/N`, `/discussions/N` | [subskills/github/SUBSKILL.md](subskills/github/SUBSKILL.md) |
| x | `x.com` / `twitter.com` posts (`…/status/<id>`) | [subskills/x/SUBSKILL.md](subskills/x/SUBSKILL.md) |
| hn | `news.ycombinator.com/item?id=<id>` | [subskills/hn/SUBSKILL.md](subskills/hn/SUBSKILL.md) |
| file | a local path (`~/…`, `./…`, `file://…`) or a document URL (`.pdf`, `.docx`, `.epub`, …) | [subskills/file/SUBSKILL.md](subskills/file/SUBSKILL.md) |

`python3 $S/shared/route.py "<input>"` shows the routing without fetching anything.

- **Exit code 2** means a missing tool. The message names the source's installer: tell the user, run
  `$S/<source>/install-prerequisites.sh`, and retry. `$S/check-prerequisites.sh` checks every source at once.
- **Exit code 1** is an expected error (unsupported input, not found, blocked). Show the message; it names the
  fallback that was tried.
- If `summary_exists` is true and the user did not ask for a new mode or language, show the existing page
  (`python3 $S/shared/render_html.py "<dir>" --open`) instead of rewriting it.
- A playlist or channel (`kind: playlist|channel`) prints a list of items instead: prepare every item where
  `summary_exists` is false (parallel subagents when there are more than 3), then write the digest (step 6).

## 2. Read the subskill

Read the envelope's `subskill` file. It says what that source needs beyond this file: extra flags, how to read its
content file, what to emphasize, and how to fill the related section. Read it before choosing the mode.

## 3. Choose the mode

| Mode | When |
|---|---|
| `summary` (default) | Nothing specific asked |
| `tldr` | "gist", "quick", "is it worth reading/watching" |
| `detailed` | Lectures, papers, long docs, "notes", "study" |
| `wisdom` | Podcasts, interviews, essays, "ideas", "insights", "takeaways" |
| `qa` | The user asked a specific question about it |
| `chapters` | Videos only: has chapters or runs longer than ~20 min, and the user wants structure |

The shape of each mode is in `<skill-dir>/templates/shared/<mode>.md` (`chapters`: the envelope's `template`).
Read the mode you picked **and** the envelope's `template`: it holds the source's related section and anything
else that source adds.

## 4. Read and write

- Read the `content_file`. For more than ~150k words, work part by part (chapters, sections, pages).
- Write the body in the template's shape, in the user's language unless they ask otherwise. The frontmatter and
  the title header come from the script, so leave them out.
- **Copy anchor links from the content file** (timestamps, paragraph links, line links, comment permalinks, page
  links). Never build them yourself.
- Never add content that isn't in the content file. Transcripts and OCR mishear names and jargon: correct them
  using the title and description. If the content looks garbled, say so in one line at the end.
- Discussions (HN threads, X replies, GitHub issues): follow
  [subskills/shared/discussion.md](subskills/shared/discussion.md): themes with attributed verbatim quotes.

## 5. Links

End every summary (except `qa`) with the links section from `templates/shared/links.md`, then the source's related
section from its `template`. Look every link up with web search and never guess a URL: the rules for books,
Wikipedia terms, repos, papers, dates and broken links are in [subskills/shared/links.md](subskills/shared/links.md).

## 6. Save

```bash
python3 $S/shared/save_summary.py "<dir>" --mode <mode> --summary-lang <xx> --model <your model id> --open <<'EOF'
<body>
EOF
```

- It writes `summary.md` (frontmatter + header from `metadata.json`) and `summary.html`, checks every link and
  writes its date after it (`BROKEN LINK:` lines: fix or drop the link and save again), records the agentic CLI
  (auto-detected; pass `--agent <name>` if the output shows none or the wrong one), and rebuilds the library index
  `<root>/library.js`.
- `--open` starts the local library server (`serve_library.py`, http://127.0.0.1:8765, in the background) and
  opens the page. The page has a sidebar with every summary (folder tree / date / title / author, each ascending or
  descending), the source's header panel (e.g. the video player), the summary and the full content file. Every
  link opens in a new tab; the sidebar links navigate in place.
- **Don't paste the summary into the chat.** Reply with the TL;DR, the path to `summary.html`, and one line for
  anything still running in the background (e.g. a video download).

## 7. Digest (playlists, channels, several inputs)

Read each item's `summary.md` and write `templates/shared/digest.md`: rank the items by how worth the user's time
they are, and pull out the themes they share and where they disagree. Save it with
`python3 $S/shared/save_summary.py "<digest_dir>" --mode digest --model <your model id> --open <<'EOF' ... EOF`.

## Follow-up questions

Re-run step 1 for the same input. It returns the existing folder instantly. Answer from the `content_file` in `qa`
shape, and only save the answer when the user asks.

## Shared scripts (`scripts/shared/`)

| Script | Does |
|---|---|
| `prepare.py` | route → `scripts/<source>/prepare.py` → envelope (checks the contract) |
| `route.py` | input → `{source, kind, id, url or path}`, no network |
| `save_summary.py` | body on stdin → `summary.md` / `digest.md` with frontmatter + header + agent, link dates, HTML page |
| `check_links.py` | checks every external link: ok / unverified / broken, plus its dates; `--annotate` writes them in |
| `check_quotes.py` | every quote in a summary body must be verbatim in the content file; lists the ones that are not |
| `link_dates.py` | how current a link is: publish date, release + last commit, package version, book year, wiki edit |
| `render_html.py` | `summary.md` → `summary.html` (sidebar, header panel, content file); `--open` |
| `library.py` | rebuild `<root>/library.js`; `--pages` re-renders every page; `--open-last` opens the latest summary |
| `serve_library.py` | local http server for the library (embeds, video seeking, download button); `--ensure`, `--stop` |

Each source's own scripts are listed in its subskill. Every `scripts/<source>/` that calls external tools has
`check-prerequisites.sh` and `install-prerequisites.sh`; `$S/check-prerequisites.sh` / `$S/install-prerequisites.sh
[--source <s>]` run them all.

The library root is `~/me/summaries` (`TELL_ME_ROOT` overrides it): `videos/<platform>/<channel>/<title>/`,
`articles/<site>/<title>/`, `repos/github/<owner>/<repo>/`, `posts/x/<user>/<words>-<id>/`,
`discussions/hn/<title>-<id>/`, `documents/<folder>/<file>/`. A video library from before this layout is migrated
once with `python3 $S/video/migrate_library.py --apply` (dry run without `--apply`).
Tests: `$S/run-tests.sh`.

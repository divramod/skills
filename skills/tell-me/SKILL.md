---
name: tell-me
description: Summarize a video, playlist or channel from a URL (YouTube first; also TikTok, X, Vimeo, podcasts and any yt-dlp-supported site) into a markdown note in ~/me/summaries/videos. Captions via yt-dlp with a local Whisper fallback, video download (best quality, in the background; --skip-download to skip), keyframes for visual content, a links section (books, Wikipedia terms, tools, further reading), and modes tldr/summary/chapters/detailed/wisdom/qa. Use when the user pastes a video link and wants a summary, the gist, notes, or answers about it; called without a link it opens the last summarized video in the browser.
---

# tell-me

Scripts do all deterministic work: fetching, folders, downloads, timestamp links, frames and file writing.
Your job is the judgment: pick the mode, read, write the summary, and check it against the transcript.
`S=<skill-dir>/scripts`. Every script prints what it did; JSON goes to stdout and progress to stderr.

## 0. No link given

When the skill is called without a URL, open the most recently summarized video and stop:

```bash
python3 $S/library.py --open-last
```

Tell the user which video opened (the printed path) and the URL. If it fails because there are no summaries yet,
ask for a link.

## 1. Prepare

```bash
python3 $S/prepare_video.py "<url>" [--skip-download] [--visual] [--lang xx]
```

- The video is **always downloaded and kept** in the **highest available quality** (up to 4K: mp4, or mkv when the
  best streams don't fit mp4; no re-encoding); an earlier lower-quality file is upgraded. The download runs **in the
  background** (`video_download.status: running` in the JSON), so carry on with steps 2–4 without waiting: when it
  finishes it adds the video to `metadata.json`, `summary.md` and `summary.html` by itself.
- Pass `--skip-download` only when the user says not to download or keep the video. The summary page then offers a
  **Download video** button instead.
- Pass `--visual` when the video is visual: slides, code, UI demos, diagrams, or a user asking "what does it show".
  The script then waits for the download (frames need it), fetching the transcript in parallel. With
  `--skip-download` it fetches only a <=1080p copy for the frames.
- Exit code 2 means a missing tool: run `$S/install-prerequisites.sh` (after telling the user) and retry.
- A bot check or HTTP 429 in the output means retry with `--cookies-from-browser chrome`. If that fails too, run `$S/install-prerequisites.sh --upgrade`.
- The Whisper fallback can take minutes. Run it in the background and tell the user.

Read the JSON output. If `summary_exists` is true and the user did not ask for a new mode or language, show the
existing `summary.html` (`python3 $S/render_html.py "<dir>" --open`) instead of rewriting it.

For a **playlist or channel URL**, run `python3 $S/list_videos.py "<url>" [--limit N]` first, then do steps 1–4 for every
video where `summary_exists` is false. Use parallel subagents when there are more than 3. Finish with step 5.

## 2. Choose the mode

| Mode | When |
|---|---|
| `summary` (default) | Nothing specific asked |
| `tldr` | "gist", "quick", "is it worth watching" |
| `chapters` | The video has chapters or runs longer than ~20 min, and the user wants structure |
| `detailed` | Lectures, courses, "notes", "study" |
| `wisdom` | Podcasts, interviews, "ideas", "insights", "takeaways" |
| `qa` | The user asked a specific question about the video |

The output shape for each mode is in `<skill-dir>/templates/<mode>.md`. Read the one you picked.

## 3. Read and write

- Read `transcript.md`. For more than ~150k words, work chapter by chapter. With `--visual`, also read
  `frames/index.md` and look at the frames that matter: slides, code, diagrams.
- Write the body in the template's shape, in the user's language unless they ask otherwise. The frontmatter and title header come from the script, so leave them out.
- **Copy timestamp links from `transcript.md`.** Never build them yourself.
- Auto-captions and Whisper mishear names and jargon. Correct them using the title and description, and never add content that isn't in the transcript or frames.
- If `transcript_source` is auto-generated or Whisper and the text looks garbled, say so in one line at the end.

### Links section

End every summary (except `qa`) with the links section and the similar videos from `templates/links.md`. It turns
the video into a reading and watching list: slides (lectures), GitHub repos, whatever the video mentions (books,
theories, frameworks, tools, papers, people), Wikipedia for the terms a reader needs, a short "Further reading" list
on the video's topic, and similar videos to watch next.

- **Look every link up with web search; never guess a URL.** Only link what you found.
- **Books:** the Amazon product page (`https://www.amazon.com/dp/<ASIN>`), which has the description and reviews.
  If there is none, use Goodreads or the publisher's page. Name the author and say in one line what the book is about.
- **Terms, theories, frameworks:** the English Wikipedia article, only for terms that matter for the summary. Skip
  everyday words.
- **Slides (lectures, talks, courses):** start with `description_links.slides` from the prepare JSON, then search the
  course or conference page. Skip the sub-section for videos that aren't lectures or talks.
- **GitHub repos:** every repo the video shows, uses or names, plus `description_links.repos`. Link the repo, not the
  author's profile.
- **Tools and projects:** the official site. **Papers:** arXiv, DOI or the publisher's page.
- "Mentioned in the video" holds only what the transcript names, with its timestamp link. Anything else goes under
  "Further reading" (3-5 of the best sources on the topic: official docs, the original paper, a good explainer, a
  counterpoint), so it's always clear what the speaker said and what you added.
- **Similar videos:** pick 2-4 search queries (the topic, the key concepts, the speaker or channel plus the topic)
  and run `python3 $S/similar_videos.py "<dir>" --query "<q1>" --query "<q2>"`. Choose 4-6 of the results, best
  first, and say in one line what each adds. Each result has its `published` date: prefer recent videos when the
  topic moves fast. Only link videos from its output. Where a result has a `summary`
  path, also add `([summary](<that path>))`.
- **Dates are added for you.** When you save, `save_summary.py` checks every link and writes how current it is right
  after it: videos, papers and articles get their publish date; GitHub repos their latest release (version + date)
  and last commit on the default branch; packages their latest version; books the first-publication year; Wikipedia
  the last edit. Never write dates yourself. To look at dates before saving (e.g. to prefer recent sources), run the
  check below.
- Fix or drop every link reported as broken (`BROKEN LINK:` when saving, `broken` below). `unverified` means the
  site blocks scripts (often Amazon): keep those links when your web search showed the page.

```bash
python3 $S/check_links.py <<'EOF'
<body>
EOF
```

To refresh the dates of an existing summary later (new releases, new commits):
`python3 $S/check_links.py --folder "<dir>" --annotate`.

## 4. Save

```bash
python3 $S/save_summary.py "<dir>" --mode <mode> --summary-lang <xx> --model <your model id> --open <<'EOF'
<body>
EOF
```

- The script records which agentic CLI wrote the summary (`agent` in the frontmatter and `metadata.json`). It is
  auto-detected (Claude Code, Codex, Grok, Gemini CLI, …). If the output shows no `agent`, or shows the wrong one,
  pass `--agent <name>` (e.g. `--agent grok`).
- It writes `summary.md` plus `summary.html` and rebuilds the library index (`<root>/library.js`). `--open` starts
  the local library server (`serve_library.py`, http://127.0.0.1:8765, in the background) and opens the page there.
  The page has a sidebar with every summary (folder tree / download date / title / author, each ascending or
  descending), a player (the local video, else the YouTube embed; timestamps seek it), keyframes and the transcript.
  With a local video the page has a **Delete downloaded video** button (it asks for confirmation first; the page then
  falls back to the YouTube player). Without a local video the page has a **Download video** button: the server runs the same download that
  `prepare_video.py` does by default (best quality, same folder) and the page switches to the local file when it's done.
- Every link on the page opens in a new tab, so the summary stays open; the sidebar links navigate in place.
- Downloaded videos carry the title, channel, date, URL and chapters as file metadata, so players like VLC show the
  title instead of `video.mkv`. For a video downloaded before that, run `python3 $S/download_video.py "<dir>" --tag`.
- **Don't paste the summary into the chat.** Reply with the TL;DR, the path to `summary.html`, and a one-line note if
  the video download is still running in the background. The folder holds `summary.md`, `summary.html`,
  `transcript.md`, `metadata.json`, and `video.<ext>` / `frames/` when those were requested.

## 5. Digest (playlists and channels only)

Read each video's `summary.md` and write `templates/digest.md`: rank the videos by how worth watching they are, and pull out the themes they share.
Save it with `python3 $S/save_summary.py "<digest_dir>" --mode digest --model <your model id> --open <<'EOF' ... EOF`.

## Follow-up questions

Re-run step 1 for the same URL. It returns the existing folder instantly. Answer from `transcript.md` in `qa` shape,
and only save the answer when the user asks.

## Scripts

| Script | Does |
|---|---|
| `prepare_video.py` | metadata → folder → [video in background] → transcript (captions, else Whisper) → [frames]; reuses folders by video id |
| `download_video.py` | video download (detached by default, status in `.video-download.json`), then metadata + chapters into the file; `--tag`, `--delete` |
| `similar_videos.py` | YouTube search for the agent's queries → similar videos (deduped, marks already-summarized ones) |
| `list_videos.py` | playlist/channel → video list + digest folder |
| `extract_frames.py` | scene-change keyframes → `frames/` + `index.md` (called by `--visual`) |
| `save_summary.py` | body on stdin → `summary.md` / `digest.md` with frontmatter + header + agent, then the HTML page |
| `check_links.py` | checks every external link: ok / unverified / broken, plus its dates; `--annotate` writes them in |
| `link_dates.py` | how current a link is: publish date, release + last commit, package version, book year, wiki edit |
| `render_html.py` | `summary.md` → `summary.html` (sidebar, player, keyframes, transcript); `--open` |
| `library.py` | rebuild `<root>/library.js` (sidebar index); `--pages` re-renders every page; `--open-last` opens the latest summary |
| `serve_library.py` | local http server for the library (YouTube embeds, video seeking, the page's download button); `--ensure`, `--stop` |
| `check-prerequisites.sh` / `install-prerequisites.sh` | check / install yt-dlp, ffmpeg, python3, uv |

The library root is `~/me/summaries/videos/<platform>/<user>/<title>/`, and `DM_SUMMARIZE_VIDEO_ROOT` overrides it.
Tests: `cd $S && python3 -m unittest discover -p 'test_*.py'`.

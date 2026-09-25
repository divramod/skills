---
name: dm-summarize-video
description: Summarize a video, playlist or channel from a URL (YouTube first; also TikTok, X, Vimeo, podcasts and any yt-dlp-supported site) into a markdown note in ~/me/summaries/videos. Captions via yt-dlp with a local Whisper fallback, optional video download (-d), keyframes for visual content, and modes tldr/summary/chapters/detailed/wisdom/qa. Use when the user pastes a video link and wants a summary, the gist, notes, or answers about it.
---

# dm-summarize-video

Scripts do all deterministic work: fetching, folders, downloads, timestamp links, frames and file writing.
Your job is the judgment: pick the mode, read, write the summary, and check it against the transcript.
`S=<skill-dir>/scripts`. Every script prints what it did; JSON goes to stdout and progress to stderr.

## 1. Prepare

```bash
python3 $S/prepare_video.py "<url>" [-d] [--visual] [--lang xx]
```

- Pass `-d` / `--download` when the user asks to download or keep the video. It always fetches the **highest available
  quality** (up to 4K: mp4, or mkv when the best streams don't fit mp4; no re-encoding) and upgrades an earlier
  lower-quality file. Warn that 4K files can be several hundred MB.
- Pass `--visual` when the video is visual: slides, code, UI demos, diagrams, or a user asking "what does it show".
  On its own it downloads a <=1080p copy, which is enough for frames. Combine it with `-d` to keep the best quality.
- Exit code 2 means a missing tool: run `$S/install-prerequisites.sh` (after telling the user) and retry.
- A bot check or HTTP 429 in the output means retry with `--cookies-from-browser chrome`. If that fails too, run `$S/install-prerequisites.sh --upgrade`.
- The Whisper fallback can take minutes. Run it in the background and tell the user.

Read the JSON output. If `summary_exists` is true and the user did not ask for a new mode or language, show the
existing `summary.md` instead of rewriting it.

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

## 4. Save

```bash
python3 $S/save_summary.py "<dir>" --mode <mode> --summary-lang <xx> <<'EOF'
<body>
EOF
```

Then show the user the summary, plus the folder path. The folder holds `summary.md`, `transcript.md`, `metadata.json`,
and `video.<ext>` / `frames/` when those were requested.

## 5. Digest (playlists and channels only)

Read each video's `summary.md` and write `templates/digest.md`: rank the videos by how worth watching they are, and pull out the themes they share.
Save it with `python3 $S/save_summary.py "<digest_dir>" --mode digest <<'EOF' ... EOF`.

## Follow-up questions

Re-run step 1 for the same URL. It returns the existing folder instantly. Answer from `transcript.md` in `qa` shape,
and only save the answer when the user asks.

## Scripts

| Script | Does |
|---|---|
| `prepare_video.py` | metadata → folder → [video] → transcript (captions, else Whisper) → [frames]; reuses folders by video id |
| `list_videos.py` | playlist/channel → video list + digest folder |
| `extract_frames.py` | scene-change keyframes → `frames/` + `index.md` (called by `--visual`) |
| `save_summary.py` | body on stdin → `summary.md` / `digest.md` with frontmatter + header |
| `check-prerequisites.sh` / `install-prerequisites.sh` | check / install yt-dlp, ffmpeg, python3, uv |

The library root is `~/me/summaries/videos/<platform>/<user>/<title>/`, and `DM_SUMMARIZE_VIDEO_ROOT` overrides it.
Tests: `cd $S && python3 -m unittest discover -p 'test_*.py'`.

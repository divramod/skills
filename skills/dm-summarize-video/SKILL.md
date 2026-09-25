---
name: dm-summarize-video
description: Summarize a video from a URL (YouTube first; also TikTok, X, Vimeo, podcasts and any yt-dlp-supported site). Fetches captions with yt-dlp, falls back to local Whisper transcription, then writes a chaptered summary with timestamp links. Use when the user pastes a video link and asks to summarize, get the gist of, or take notes from it.
---

# dm-summarize-video

Turn a video URL into a timestamped transcript, then summarize it yourself.
The script only fetches text. You, the agent, write the summary, so no extra LLM or API key is needed.

## Requirements

- `yt-dlp` and `ffmpeg` on PATH (`brew install yt-dlp ffmpeg`)
- `uv` only for the Whisper fallback (runs `mlx-whisper` on Apple Silicon, `openai-whisper` elsewhere, via `uvx`)

## Workflow

1. **Fetch the transcript**:

   ```bash
   python3 <skill-dir>/scripts/fetch_transcript.py "<url>"
   ```

   The last stdout line is the path to `transcript.md`. Progress goes to stderr.
   The script tries captions first (manual, then auto-generated, one track only). If none exist, it downloads the
   audio and transcribes it with Whisper. Results are cached per video in `~/.cache/dm-summarize-video/<platform>-<id>/`.

   Useful flags:
   - `--lang de`: preferred transcript language (default: the spoken language)
   - `--source captions|whisper`: force one path (default `auto`)
   - `--cookies-from-browser chrome`: use when YouTube answers "Sign in to confirm you're not a bot" or HTTP 429
   - `--refresh`: ignore the cache

   Whisper runs can take minutes, and the first run downloads the model (~1.5 GB). Run it in the background and tell the user.

2. **Read `transcript.md`**. It contains the metadata, the chapters, the description and the transcript as `[mm:ss]` paragraphs.
   For very long transcripts (more than ~150k words), summarize chapter by chapter, then merge.

3. **Write the summary** in the user's language unless they ask otherwise:

   ```markdown
   # <title>
   <channel> · <duration> · <published> · <url>

   **TL;DR:** 2–3 sentences.

   ## Key points
   - point ([mm:ss](<url>&t=<seconds>s))

   ## Chapter summaries   (only if the video has chapters or runs longer than ~15 min)
   ### <chapter> ([mm:ss](<url>&t=<seconds>s))
   - …

   ## Notable quotes / numbers / resources mentioned
   ```

   - For timestamp links, use `&t=<seconds>s` on `watch?v=` URLs and `?t=<seconds>` on `youtu.be` URLs. On other platforms, write plain `mm:ss`.
   - Auto-generated captions and Whisper both mishear names and jargon. Fix obvious errors using the title
     and description as context, and do not invent content that is not in the transcript.
   - Say so if the transcript source is auto-generated and the quality looks poor.
   - If the user asked a specific question about the video, answer it first and cite timestamps.

4. **Follow-up questions** reuse the cached `transcript.md`. Re-run the script for the same URL and it returns instantly.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Sign in to confirm you're not a bot` / HTTP 429 | `--cookies-from-browser <browser>`, wait, or `brew upgrade yt-dlp` |
| Extractor error on a non-YouTube site | `brew upgrade yt-dlp` (site extractors break often) |
| `no usable captions` with `--source captions` | Drop the flag so it falls back to Whisper |
| Private or members-only video | `--cookies-from-browser` with a logged-in browser |

## Tests

```bash
cd <skill-dir>/scripts && python3 -m unittest test_fetch_transcript.py
```

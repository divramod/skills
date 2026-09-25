# video

YouTube (videos, playlists, channels), youtu.be, Vimeo, TikTok, X videos, podcasts and any other yt-dlp site.
The content file `content.md` is the transcript with timestamp links, chapters and the description.

## Flags

```bash
python3 $S/shared/prepare.py "<url>" [--skip-download] [--visual] [--lang xx] [--limit N]
```

- The video is **always downloaded and kept** in the **highest available quality** (up to 4K: mp4, or mkv when the
  best streams don't fit mp4; no re-encoding); an earlier lower-quality file is upgraded. The download runs **in the
  background** (`video_download.status: running` in the envelope), so carry on without waiting: when it finishes it
  adds the video to `metadata.json`, `summary.md` and `summary.html` by itself.
- `--skip-download` only when the user says not to download or keep the video. The page then offers a **Download
  video** button instead.
- `--visual` when the video is visual: slides, code, UI demos, diagrams, or a user asking "what does it show". The
  script then waits for the download (frames need it) while it fetches the transcript. With `--skip-download` it
  fetches only a <=1080p copy for the frames. Then also read `frames/index.md` and look at the frames that matter.
- `--lang xx` picks the transcript language (default: the spoken language).
- A bot check or HTTP 429 in the output means retry with `--cookies-from-browser chrome`. If that fails too, run
  `$S/video/install-prerequisites.sh --upgrade` (yt-dlp ages fast).
- Without captions the transcript comes from local Whisper, which can take minutes. Run it in the background and
  tell the user.
- **Playlists and channels** print `kind: playlist|channel` with the videos (channels: the latest 10, `--limit N`).
  Prepare and summarize every video where `summary_exists` is false, then write the digest.

## Writing

- `transcript_source` says where the text came from. Auto-captions and Whisper mishear names and jargon: fix them
  from the title and description. If an auto-generated or Whisper transcript looks garbled, say so in one line.
- Use `chapters` mode (in `templates/video/template.md`) when the video has chapters or runs longer than ~20 min and
  the user wants structure.
- Lectures and talks: fill "Slides & course materials" (template) from `description_links.slides`, then search the
  course or conference page. Add `description_links.repos` under GitHub repos.

## Similar videos (related section)

Pick 2-4 search queries (the topic, the key concepts, the speaker or channel plus the topic) and run
`python3 $S/video/related.py "<dir>" --query "<q1>" --query "<q2>"`. Choose 4-6 of the results, best first, and say in
one line what each adds. Each result has its `published` date: prefer recent videos when the topic moves fast. Only
link videos from its output; where a result has a `summary` path, also add `([summary](<that path>))`.

## Page and files

The page's player is the local video, else the YouTube embed; timestamp links seek it. With a local video the page
has a **Delete downloaded video** button (asks first; the page falls back to YouTube). Downloaded videos carry the
title, channel, date, URL and chapters as file metadata (players like VLC show the title); for a video downloaded
before that, run `python3 $S/video/download_video.py "<dir>" --tag`. The folder holds `summary.md`, `summary.html`,
`content.md`, `metadata.json`, and `video.<ext>` / `frames/` when those were requested.

## Scripts (`scripts/video/`)

| Script | Does |
|---|---|
| `prepare.py` | metadata → folder → [video in background] → transcript (captions, else Whisper) → [frames]; reuses folders by video id; playlists/channels via `list_videos.py`; `--dir <folder> --content-part video` makes the video a part of another item (an x post: `video-transcript.md`, no `videos/…` entry) |
| `download_video.py` | video download (detached by default, status in `.video-download.json`), then metadata + chapters into the file; `--tag`, `--delete`, `--status` |
| `related.py` | YouTube search for your queries → similar videos (deduped, marks already-summarized ones) |
| `list_videos.py` | playlist/channel → video list + digest folder |
| `extract_frames.py` | scene-change keyframes → `frames/` + `index.md` (called by `--visual`) |
| `migrate_library.py` | one-off: a video library from before the multi-source layout → `content.md` + contract fields |

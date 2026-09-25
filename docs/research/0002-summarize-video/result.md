---
name: summarize-video
description: Survey of the top 10 ways to summarize a video from a URL (Sep 2026) — yt-dlp captions → agent LLM is the best default for a skill; Whisper fallback and Gemini native video are the strongest complements.
status: in_progress
scope: global
created: 2026-09-25
---

# Research: summarize-video

## Question

We want a skill `skills/dm-summarize-video` that summarizes a video from a URL —
YouTube first, other platforms later. Which methods exist, which are popular,
and which one should the skill implement?

## TL;DR

- Nearly every tool follows the same pipeline: **get text (captions or ASR) → optionally chunk → LLM summary**.
  The tools differ mainly in how they get the text and whether they also look at the frames.
- For an agent skill, the host agent (Claude) already *is* the LLM. The skill only needs a
  robust **transcript fetcher script**. That makes **yt-dlp captions** the best default:
  it is free, needs no key, and covers 1800+ sites. Local Whisper fills the gap for videos without captions.
- **Gemini native video** (`file_data.file_uri = <youtube url>`) is the only method that also
  *sees* the video, but it needs an API key, is limited to public YouTube videos, and sends the video to Google.
- The big 2026 risk is **YouTube bot detection** ("Sign in to confirm you're not a bot", 429s).
  This mostly affects cloud IPs. On a home machine it is manageable with `--cookies-from-browser`.

## Top 10 methods

| # | Method | How it works | Strengths | Weaknesses |
|---|--------|--------------|-----------|------------|
| 1 | **yt-dlp captions → LLM** | `yt-dlp --skip-download --write-subs --write-auto-subs` → strip VTT → prompt | Free, no key; works on 1800+ sites; manual captions first, auto captions as fallback; gives chapters and metadata too | No captions → no text; auto-caption errors; bot checks/429s (need cookies); requesting many languages at once triggers 429 |
| 2 | **youtube-transcript-api (Py) / youtube-transcript (npm) → LLM** | Calls YouTube's internal caption endpoint directly | Most popular library; fast; simple JSON with timestamps | YouTube only; cloud IPs blocked (RequestBlocked/IpBlocked); breaks when YouTube changes internals |
| 3 | **Download audio → Whisper ASR → LLM** | yt-dlp `-x` → openai-whisper / whisper.cpp / mlx-whisper / Parakeet-MLX | Works without captions and on any platform; accurate; local and private; fast on Apple Silicon | Slower (minutes); model download (GBs); downloads the media; no speaker labels without diarization |
| 4 | **Cloud STT API → LLM** | Audio → OpenAI / Deepgram / AssemblyAI / Groq Whisper | Very fast; diarization and word timestamps; nothing to install locally | Costs money; needs a key; privacy; you still download the audio yourself |
| 5 | **Gemini native video understanding** | Send the YouTube URL as `file_data.file_uri` (or upload the file) | Truly multimodal (frames + audio): catches slides, code and demos; one call; 1M+ context | Needs an API key; public YouTube only; token-heavy on long videos; vendor lock-in; data goes to Google |
| 6 | **Keyframes + transcript → multimodal LLM** | ffmpeg scene detection → dedup frames (+OCR) → images + transcript to Claude | Captures visual-only info (slides, diagrams, code) with any vision LLM | Complex; token-expensive; needs the full video download; tuning (scene threshold, frame cap) |
| 7 | **All-in-one CLI (steipete/summarize, Fabric `yt` + `extract_wisdom`)** | Ready-made tool: captions → Whisper fallback → LLM, with patterns | Battle-tested; rich features (slides+OCR, podcasts, many providers); great prompt patterns (Fabric) | Extra dependency (Node 24 / Go); calls its own LLM (double cost, second key); less control from inside the skill |
| 8 | **MCP transcript server** | e.g. `kimtaeyoon83/mcp-server-youtube-transcript`, TranscriptAPI MCP | Agent fetches it natively; nothing in the repo | Per-user MCP config (not portable in a skill repo); usually YouTube only; same IP-block issues or a paid backend |
| 9 | **Managed transcript API (Supadata, TranscriptAPI, SearchAPI)** | REST call → transcript (Supadata has an AI fallback when no captions exist) | Reliable on cloud IPs (proxies included); multi-platform (Supadata); no maintenance | Paid; needs a key; third-party dependency; privacy |
| 10 | **Consumer apps (NotebookLM, Eightify, Glasp, HARPA, NoteGPT)** | Paste the link or click the extension | Zero setup; polished UX; NotebookLM does multi-video Q&A with citations | Not scriptable or agent-usable; manual; public YouTube only (NotebookLM); no control over the prompt or output |

Orthogonal to all of the above is the **summarization strategy**: single pass (fits modern
200k–1M context windows for ~99% of videos), map-reduce chunking (very long streams),
and chapter-aware summaries (use YouTube chapters as section boundaries).

## Most effective for this skill (shortlist)

1. **A — yt-dlp captions → Claude** (method 1). Minimal, free, multi-platform.
2. **B — A + local Whisper fallback** (1 + 3). Uses mlx-whisper on Apple Silicon when a video has no captions. Covers ~100% of videos.
3. **C — Gemini native video** (5). Best for visually heavy videos, but needs a key.
4. **D — Hybrid: B + optional keyframes/Gemini "visual pass"** (1 + 3 + 6/5). Most complete, and the most work.

**Recommendation: B.** Captions cover most YouTube videos instantly. Whisper covers the rest and
non-YouTube platforms (TikTok, X, Vimeo, and podcasts often have no captions). Everything runs
locally with no key, and Claude does the summary itself, so there's no second LLM bill.
yt-dlp and ffmpeg are already installed. mlx-whisper runs via `uvx`, so nothing needs a global install.

## Findings from a local test (2026-09-25)

- `yt-dlp 2026.03.17` fetched English captions for `jNQXAC9IVRw` fine.
- `--sub-langs "en.*"` also requested the machine-translated track `en-de` → **HTTP 429**.
  The script must request exactly one track (original language first) and treat per-track failures as non-fatal.
- A warning about missing `curl_cffi` impersonation appeared. Installing `yt-dlp[default,curl-cffi]` may improve resilience.

## Sources

- [Gemini API — video understanding](https://ai.google.dev/gemini-api/docs/video-understanding)
- [steipete/summarize](https://github.com/steipete/summarize) · [docs/youtube.md](https://github.com/steipete/summarize/blob/main/docs/youtube.md)
- [danielmiessler/Fabric — YouTube processing](https://github.com/danielmiessler/Fabric/blob/main/docs/YouTube-Processing.md?plain=1) · [Major Hayden: Summarize YouTube with Fabric](https://major.io/p/summarize-youtube-videos-fabric/)
- [youtube-transcript-api](https://pypi.org/project/youtube-transcript-api/) · [Cloud IP blocking issue #593](https://github.com/jdepoix/youtube-transcript-api/issues/593) · [IP-blocked guide](https://github.com/hxckya/youtube-transcript-ip-blocked-guide)
- [yt-dlp "not a bot" fix](https://yt-dlp.net/errors/sign-in-to-confirm-not-a-bot) · [PO token](https://yt-dlp.net/errors/po-token-required) · [yt-dlp #15865](https://github.com/yt-dlp/yt-dlp/issues/15865)
- [Whisper vs Parakeet on MLX (2026)](https://contracollective.com/blog/local-speech-to-text-whisper-parakeet-mlx-m5-max-2026) · [parakeet-mlx](https://github.com/EliFuzz/parakeet-mlx) · [mlx-audio](https://github.com/Blaizzy/mlx-audio)
- [Claude-Real-Video (scene-aware frames)](https://aiweekly.co/alerts/claude-real-video-feeds-scene-aware-frames-to-text-only-llms) · [video-frames-skill](https://github.com/mugnimaestra/video-frames-skill) · [EftikharAzim/youtube-to-skill](https://github.com/EftikharAzim/youtube-to-skill)
- [hancengiz/youtube-transcript-mcp](https://github.com/hancengiz/youtube-transcript-mcp) · [3 ways to use YouTube with Claude Code](https://awesomeclaude.ai/how-to/use-youtube-with-claude)
- [Best YouTube transcript APIs 2026](https://transcriptapi.com/blog/best-youtube-transcript-apis-compared) · [sipsip: summarizer API architecture](https://sipsip.ai/blog/youtube-video-summarizer-api)
- [NotebookLM audio + YouTube sources](https://blog.google/innovation-and-ai/products/notebooklm-audio-video-sources/) · [Unite.AI: best YouTube summarizers (Sep 2026)](https://www.unite.ai/youtube-summarizer-tools/)

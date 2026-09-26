# Plan grill — phase 007 — 2026-09-25 (self-review, auto-accept)

| # | Finding | Resolution |
|---|---|---|
| 1 | Moving the digest logic out of `list_videos.py` touches video files during wave 02 while 005 is also working in video | `digest_dir()` moves into `shared/_common.py`; `list_videos.py` only changes one import line |

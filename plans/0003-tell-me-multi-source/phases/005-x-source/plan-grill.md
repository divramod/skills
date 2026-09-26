# Plan grill — phase 005 — 2026-09-25 (self-review, auto-accept)

| # | Finding | Resolution |
|---|---|---|
| 1 | Calling `video/prepare.py` on the post URL would create a second library entry under `videos/x/…` | T403: new `--dir` / `--content-part video` flags write the transcript and download into the x folder |

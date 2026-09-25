# Plan grill — phase 001 — 2026-09-25 (self-review, auto-accept)

| # | Finding | Resolution |
|---|---|---|
| 1 | `serve_library.py` (shared) imports `download_status`, `delete_video` and `start_background` from `download_video` (video). That breaks the rule that shared code never imports source code. | T001: serve_library calls `video/download_video.py` as a subprocess; add `--status` JSON output. |
| 2 | `unittest discover -s . -t .` finds no tests in subfolders without `__init__.py` | spec criterion + Commands changed to a per-folder loop |
| 3 | `render_html` imports `library` (both shared) | fine, no change |

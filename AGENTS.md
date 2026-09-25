<!-- THIS IS A HAL PROJECT. run hal project --help to understand what it means -->
<!-- hal-version: 0.1.88 -->

## Verify Your Work

Before finishing any task:
1. Can you verify changes work? (compile, run, execute) → Do it.
2. Can you run existing tests? → Run them.
3. No tests cover your change? → Write one.
4. No way to test? → State what you couldn't verify.

## Skill script rules

Skills keep deterministic work (fetching, parsing, file layout, downloads, formatting) in `skills/<name>/scripts/`;
`SKILL.md` holds only the non-deterministic work (judgment, writing, choosing) plus the script calls.

When a skill's scripts call external command-line tools (yt-dlp, ffmpeg, uvx, jq, ...):

1. **Every script checks each tool before using it** and exits non-zero with a clear message that names the missing
   tool and how to install it. Python scripts: `shutil.which()` (see `skills/tell-me/scripts/shared/_common.py`
   `require()`). Bash scripts: `command -v <tool>`.
2. **Every scripts folder that calls tools ships `check-prerequisites.sh`**: `scripts/` for a flat skill, and each
   per-source `scripts/<folder>/` for a split one (e.g. `skills/tell-me/scripts/video/`). It checks every required
   and optional tool of that folder, prints `ok` or `MISSING <tool> -> <install command>`, and exits 1 when a
   required tool is missing.
3. **… and `install-prerequisites.sh`**: it installs only that folder's missing tools (Homebrew first, then
   apt-get) and finishes by running its `check-prerequisites.sh`. A split skill also keeps both scripts at the top of
   `scripts/` as aggregators that run every folder's (`--source <folder>` for one).
4. All of them are executable. `SKILL.md` tells the agent to run the folder's `install-prerequisites.sh` when a
   script exits with a missing-tool error (exit 2; the message names the script).

`python3 scripts/check-plugins.py` enforces 2–4 per folder (a folder counts as using tools when one of its own
scripts contains `subprocess`, `shutil.which`, `command -v` or `os.system(`). Its tests:
`python3 -m unittest discover -s scripts`.

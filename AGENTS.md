<!-- THIS IS A HAL PROJECT. run hal project --help to understand what it means -->
<!-- hal-version: 0.1.88 -->

## Verify Your Work

Before finishing any task:
1. Can you verify changes work? (compile, run, execute) → Do it.
2. Can you run existing tests? → Run them.
3. No tests cover your change? → Write one.
4. No way to test? → State what you couldn't verify.

## Skill data location

A skill that creates data of its own (summaries, downloads, caches, indexes) keeps it under
`~/skills/<skill-name>/`, one folder per source or kind below it (`~/skills/<skill-name>/<source>/`), never in a
shared folder such as `~/me/summaries/`. An environment variable may override the root (`<SKILL_NAME>_ROOT`). When
the default location changes and data is still at the old one, the skill stops with the command that moves it; it
never moves or silently reuses it.

## Deterministic first

Whatever can be done deterministically is done deterministically, by a skill's scripts or a CLI. The model does
only the judgment steps, and loops tick as code that wakes the model only for judgment work:
[.adr/deterministic-first.md](.adr/deterministic-first.md).

## Skill shape

Every `SKILL.md` has front matter `name` (its folder's name) and `description`, one `# ` heading, and a table of
calls (rows starting with `` `/<name>` ``) before the first numbered section, with a `/<name> h` row; a
`SUBSKILL.md` has one `# ` heading. hal2's `hal2-cli-records check` holds it (the Skill kind, opted into by
`.hal/records.toml`, which also excludes the generated shortcut skills `c` and `h`).

## Skill script rules

Skills keep deterministic work (fetching, parsing, file layout, downloads, formatting) in `skills/<name>/scripts/`,
or in a CLI of their own (tell calls hal2's `hal2-cli-tell` and has no scripts); `SKILL.md` holds only the
non-deterministic work (judgment, writing, choosing) plus the script or CLI calls.

When a skill's scripts call external command-line tools (yt-dlp, ffmpeg, uvx, jq, ...):

1. **Every script checks each tool before using it** and exits non-zero with a clear message that names the missing
   tool and how to install it. Python scripts: `shutil.which()`. Bash scripts: `command -v <tool>`.
2. **Every scripts folder that calls tools ships `check-prerequisites.sh`**: `scripts/` for a flat skill, and each
   per-source `scripts/<folder>/` for a split one (e.g. `scripts/video/`). It checks every required
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

No skill script starts an agent session itself or types `/exit` (hal2 plan 0212): a session starts through hal2
(`hal2-cli-git worktree run`, `hal2-cli-agents spawn`, create-worktree-session's create.py), so it is named and
reachable by Remote Control, and stops through `hal2-cli-agents stop`. `python3 scripts/check-agent-starts.py`
checks it; the same `unittest discover -s scripts` runs it over the repository.

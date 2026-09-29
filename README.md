# divramod/skills

Agent skills by [divramod](https://github.com/divramod). They work in **Claude Code**, **Codex**, **Grok Build**, **OpenCode**
and every other harness that reads the [Agent Skills](https://agentskills.io) `SKILL.md` format.

## Skills

| Skill | What it does |
|---|---|
| [handoff](./skills/handoff/SKILL.md) | Hand off before `/clear` without losing context: records every decision from the conversation in the repo's intent doc (`INTENT.md`), then rewrites `HANDOFF.md` with the goal, a link to the plan (`CURRENT_PLAN` or a plan file) and its current step, what is done, the next tasks with a done-when check, traps, open decisions and the prompt to start with; commits only those docs. `/handoff continue` reads it back and carries on. |
| [plan](./skills/plan/SKILL.md) | Lean planning: one self-contained folder per plan, `plans/<NNNN>-<slug>/plan.md` plus its helper files (goal, steps with a done-when check and status, decisions), `plans/CURRENT_PLAN` names the active one for the statusline; research gets a research plan `<NNNN>-research-<topic>`. `/plan new [--research]`, `/plan`, `/plan n` (run it: offers `/grill` first, then runs step after step autonomously, commits after every step and stops for a `/handoff` at 40% context), `/plan d` (done), `/plan h` (help). |
| [grill](./skills/grill/SKILL.md) | Relentless interview about a plan or idea until every branch of its design tree is resolved: rounds through the question tool with a recommended answer each, facts looked up instead of asked, decisions written to the plan and `INTENT.md` so nothing is asked twice. Adapted from [Matt Pocock's grill-me](https://github.com/mattpocock/skills) (MIT). |
| [pause](./skills/pause/SKILL.md) | Pause all of a session's work at once: background shells are frozen (SIGSTOP) where they are, subagents, workflows and monitors are stopped with their transcripts kept, cron jobs and `/loop` wakeups are removed, and a pause record (`~/skills/pause/<checkout>.md`) notes what ran, where each piece stood and how to resume it. Nothing is committed or lost. |
| [continue](./skills/continue/SKILL.md) | Resume what `pause` paused, in the same session or a fresh one: checks for drift, thaws the frozen shells (or reruns them when gone), resumes subagents (`SendMessage`, or relaunched from the recorded task and progress), workflows, monitors, cron jobs and the `/loop`, then carries on with the main task's next action. |
| [cleanup](./skills/cleanup/SKILL.md) | Free a worktree's disk space without asking: deletes its git-ignored build artifacts as the repo's `.hal/cleanup` lists them (globs to delete, `!` globs to keep, e.g. `node_modules/`; generic patterns like `target/`, `.build/`, `dist/` without the file) and reports sizes and how each comes back; `/mtm` runs it after a fully landed worktree. Never touches tracked files, secrets, `.env`, `.hal/`, `plans/` or `shotfiles/`, and refuses while a build still runs in the worktree. |
| [mfm](./skills/mfm/SKILL.md) | merge-from-main for any repository: merges the latest default branch (main, master, ...) into the current git worktree via `hal2-cli-git`, runs the repo's setup tasks (`setup` verb scripts, `.hal/hooks.toml`) and `.hal/hooks/merge-from-main/post-merge.sh`, resolves conflicts and fixes a failing setup or hook itself. |
| [mtm](./skills/mtm/SKILL.md) | merge-to-main for any repository, so several worktrees can work in parallel: commits all work (gitignores junk, never commits secrets, asks about unclear files), then lands the worktree through `hal2-cli-git` and the repo's hooks (per-app verb scripts with inherited defaults and settings in `.hal/hooks.toml`, only for changed code, run as a parallel task graph) as one merge commit on the default branch, pushes and resets the worktree; resolves conflicts and fixes failing hooks itself. `/mtm config` sets up the tasks app by app with `hal2-cli-hooks` (setup and the lint/build/test gates before landing, version bumps in the merge commit, install and deploy after it), default scripts per stack and `hal2-cli-hooks run --phase` to run a phase like a landing would. |
| [shoot](./skills/shoot/SKILL.md) | Pick the next shot from the agent CLI instead of Neovim: lists the open shots of the repo's `shotfiles/` via `hal2-cli-shooter shots list-open` as a table (id, shotfile, shot number, title), the 10 most important by default, all with `-a`, one shotfile with `/shoot <shotfile>`; the picked shot (or `/shoot <id>`) is marked sent in its shotfile and carried out in the session, like `<space>00` in hal2-nvim. |
| [tell](./skills/tell/SKILL.md) | Summarize anything from a URL or a path into `~/skills/tell/`: a video, playlist or channel (YouTube, TikTok, X, podcasts, any yt-dlp site; captions or local Whisper, background download), a web page (trafilatura + defuddle, Jina and Wayback fallbacks), a GitHub repo, issue, PR or discussion (`--deep` packs the repo with repomix), an X post or thread with its replies and video, a Hacker News thread or a Reddit post (article + discussion; Reddit falls back to an app token or the Arctic Shift archive when it blocks anonymous requests), or a document (PDF, DOCX, PPTX, EPUB, … via markitdown). A topic instead of a link (`/tell okf`) searches YouTube, the web, GitHub, Hacker News and your local documents for it, summarizes the relevant finds and writes a digest in `topics/<topic>/`. Several inputs at once get a digest. Every summary links back into its source (timestamps, paragraphs, line numbers, permalinks, pages), checks its quotes and links, lists related items, and gets a page in a browsable library with a source filter and a read-aloud button (local Supertonic-3 text-to-speech). Modes tldr/summary/chapters/detailed/wisdom/qa. Each source checks its own tools: run `scripts/<source>/install-prerequisites.sh` (or `scripts/install-prerequisites.sh` for all). |

## Install

Pick **one** route per agent. The plugin and a skills copy together give you every skill twice.

### Claude Code: plugin

```bash
claude plugin marketplace add divramod/skills
claude plugin install divramod-skills@divramod
```

Or, inside a session: `/plugin marketplace add divramod/skills`, then `/plugin install divramod-skills@divramod`.

### Codex: plugin

```bash
codex plugin marketplace add divramod/skills
codex plugin add divramod-skills@divramod
```

### Grok Build: plugin

```bash
grok plugin install divramod/skills
```

### From a local clone: links

For working on the skills themselves: link every skill into Claude Code (`~/.claude/skills`) and into the shared
folder Codex and other agents read (`~/.agents/skills`). Edits in the clone are live; renamed or removed skills
are unlinked; anything that isn't a link into the clone is left alone.

```bash
python3 scripts/install-skills.py            # --dry-run to preview, --target DIR for other folders
```

### OpenCode, and any other agent: skills.sh

OpenCode has no plugin route for skills. [skills.sh](https://skills.sh) copies the skill files into the agent's skills directory:

```bash
npx skills@latest add divramod/skills            # pick skills + agents interactively
npx skills@latest add divramod/skills -g -a opencode
```

## Develop

```bash
git clone git@github.com:divramod/skills.git && cd skills
scripts/link-skills.sh        # symlink every skill into ~/.claude/skills and ~/.agents/skills
scripts/link-skills.sh --unlink
```

The symlinks make edits live in all four agents. Claude Code reads `~/.claude/skills`. Codex, OpenCode and Grok read
`~/.agents/skills`. Use this instead of the plugins on a machine where you work on the skills.

### Layout

```
skills/<name>/SKILL.md            one folder per skill (flat, no buckets)
skills/<name>/scripts/            deterministic work; check-/install-prerequisites.sh when tools are used
.claude-plugin/plugin.json        Claude Code plugin: lists each skill explicitly
.claude-plugin/marketplace.json   makes this repo its own Claude marketplace
.codex-plugin/plugin.json         Codex plugin: ships ./skills/ (Grok reads these manifests too)
.agents/plugins/marketplace.json  makes this repo its own Codex marketplace
```

### Adding a skill

1. Create `skills/<name>/SKILL.md`. Its frontmatter `name` must equal the folder name, and it needs a `description`.
2. Add `./skills/<name>` to `.claude-plugin/plugin.json` `skills`, and a row to the table above.
3. Bump `version` in **both** `plugin.json` files. Installed plugins update only when the version changes.
4. Scripts calling external tools: add `scripts/check-prerequisites.sh` + `scripts/install-prerequisites.sh`
   (rules in [CLAUDE.md](./CLAUDE.md), "Skill script rules").
5. Run the checks:

```bash
python3 scripts/check-plugins.py
claude plugin validate . --strict
grok plugin validate .
```

## License

[MIT](./LICENSE)

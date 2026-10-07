# divramod/skills

Agent skills by [divramod](https://github.com/divramod). They work in **Claude Code**, **Codex**, **Grok Build**, **OpenCode**
and every other harness that reads the [Agent Skills](https://agentskills.io) `SKILL.md` format.

## Skills

| Skill | What it does |
|---|---|
| [handoff](./skills/handoff/SKILL.md) | Hand off before `/clear` without losing context: records every decision from the conversation in the repo's intent doc (`INTENT.md`), then rewrites `HANDOFF.md` with the goal, a link to the plan (`CURRENT_PLAN` or a plan file) and its current step, what is done, the next tasks with a done-when check, traps, open decisions and the prompt to start with; collects every question of the session with its answer in the plan's committed `questions.md` (the open ones are the first thing after the clear); commits only those docs. `/handoff continue` reads it back, asks the farmer whether a decision was forgotten (`decision check`; without a farmer it compares plan, intent doc and handoff itself) and carries on. |
| [plan](./skills/plan/SKILL.md) | Lean planning: one self-contained folder per plan, `plans/<NNNN>-<slug>/plan.md` plus its helper files (goal, steps with a done-when check and status, decisions), `plans/CURRENT_PLAN` names the active one for the statusline; research gets a research plan `<NNNN>-research-<topic>`. `/plan new [--research]`, `/plan`, `/plan n` (run it: offers `/grill` first, then runs step after step autonomously, commits after every step and stops for a `/handoff` at 40% context), `/plan d` (done), `/plan h` (help). |
| [research](./skills/research/SKILL.md) | Research a question into a cited doc, `research/<NNNN>-<slug>/research.md`: YAML front matter plus fixed H2 sections, answer first, claim-level `[S#]` citations, an evidence table, confidence with reasons, a revisit date with signposts and a premortem. `/research <question>` runs the bundled deep-research Workflow (plan → parallel researchers → independent verification of every claim → premortem → report), `/research quick` uses 1-3 subagents; numbers unique across worktrees and branches (the plan skill's numbering). `/research new\|list\|check\|verify <n>\|revisit <n>`, `/research h` (help). |
| [grill](./skills/grill/SKILL.md) | Relentless interview about a plan or idea until every branch of its design tree is resolved: rounds through the question tool with a recommended answer each, facts looked up instead of asked, decisions written to the plan and `INTENT.md` so nothing is asked twice. Adapted from [Matt Pocock's grill-me](https://github.com/mattpocock/skills) (MIT). |
| [farmer](./skills/farmer/SKILL.md) | The user's helper that gets things running in a repository and keeps them running, autonomously wherever possible; started only by the user, in its own worktree slot `farmer-<repo>` (`hal2-cli-git worktree run farmer`, then `/farmer start`, which installs a launchd/systemd timer). Each tick (`farmer.py tick`) runs every rule-based step of the opted-in duties as code and wakes the farmer's Claude session with `/farmer act` only for judgment, so a quiet round costs no model call. It never changes its own branch: fixes go to servant sessions it starts with a plan written, autogrilled and landed by the plan skill, and it logs every action; a servant's `decision check` after its clear is answered from that log as code (`farmer.py decision-check`). Duties: **merge-to-main-boss** (finished work onto main fast), **development-lead** (unstick sessions, answer what the repo decided, batch product questions), **ci** (GitHub Actions green), **sanity-watch** (resume abnormal stops), **fix-autoclear** (autoclear failures) and **merge trains** (finished branches that touch different files land as one), plus roles/farmer/ROLE.md's tasks. Its role file and every runtime file (log, state, a summary per round with actions) live in the slot's `roles/farmer/`, ignored by the folder's own `.gitignore` but `ROLE.md`. Built on hal2. |
| [pause](./skills/pause/SKILL.md) | Pause all of a session's work at once: background shells are frozen (SIGSTOP) where they are, subagents, workflows and monitors are stopped with their transcripts kept, cron jobs and `/loop` wakeups are removed, and a pause record (`~/skills/pause/<checkout>.md`) notes what ran, where each piece stood and how to resume it. Nothing is committed or lost. |
| [continue](./skills/continue/SKILL.md) | Resume what `pause` paused, in the same session or a fresh one: checks for drift, thaws the frozen shells (or reruns them when gone), resumes subagents (`SendMessage`, or relaunched from the recorded task and progress), workflows, monitors, cron jobs and the `/loop`, then carries on with the main task's next action. |
| [stop-all-agent-work](./skills/stop-all-agent-work/SKILL.md) | Stop every Claude Code session on the machine at once for a quiet system (benchmarks), except the ones you keep (`/stop-all-agent-work keep hal2/07`): through Claude Code's cross-session socket each session runs `pause` (a running `/mtm` landing is aborted and started anew later), then `quiet.py` freezes what still runs below paused sessions, ends test leftovers, shuts down simulators, quits Ollama, unloads timer LaunchAgents (e.g. an Ollama keepalive) and records every undo; system daemons, the kept sessions and your apps are only listed. |
| [continue-all-agent-work](./skills/continue-all-agent-work/SKILL.md) | The counterpart: undoes the machine quieting from the stop record (thaw, reload LaunchAgents, start Ollama, unpause containers) and tells every stopped session to `/continue`. |
| [cleanup](./skills/cleanup/SKILL.md) | Free a worktree's disk space without asking (this one, or another of the repository from any session: `/cleanup 03`): deletes its git-ignored build artifacts as the repo's `.hal/cleanup` lists them (globs to delete, `!` globs to keep, e.g. `node_modules/`; generic patterns like `target/`, `.build/`, `dist/` without the file) and reports sizes and how each comes back; `/mtm` runs it after a fully landed worktree. Never touches tracked files, secrets, `.env`, `.hal/`, `plans/` or `shotfiles/`, and refuses while a build still runs in the worktree. |
| [fix-autoclear](./skills/fix-autoclear/SKILL.md) | Fix a failure of hal2's autoclear (the context guard, the clear-and-continue job and the sweep) from screenshots and a short description: collects the evidence (job record and log, guard markers, transcript tail, sweep log), matches known cases, fixes the root cause in hal2 with a regression test from the incident, installs it, gets the stuck session going and records the case in `cases.md`; it updates its own insider knowledge and checks it against the code (`selfcheck`). `doctor` finds failures nobody reported. |
| [sanity-watch](./skills/sanity-watch/SKILL.md) | Watch every agent session of a project from a dedicated Claude session, waking every 30 minutes (`/sanity-watch start`). A script finds the sessions that stopped abnormally (API errors such as "Connection lost mid-response", network, sleep, usage limits, a turn ended early in a plan, hangs, lost processes, dialogs waiting too long) and classifies them. The watcher resumes the safe ones within a restart budget and keeps a case library of failure classes. For a new or recurring class it spawns a fresh agent in the next free worktree slot, which writes an `autogenerated` fix plan (a regression test plus more logs in the failing code), autogrills it twice and runs it to its automatic landing. Built on hal2 (`hal2-cli-agents`). |
| [fix-loc](./skills/fix-loc/SKILL.md) | Bring every file of a repository's apps, libs and scripts to at most 300 code lines, endlessly, from a dedicated Claude session (`/fix-loc start`): a scanner (scc code lines; tests, inline Rust tests and generated code out) finds the units over the limit, hotspot first, and spawns one Sonnet 5.5 worker at a time in the next free worktree slot, which writes an `autogenerated` plan for the whole unit (dead code out first, long functions, inline tests to their own files, then splits along cohesive seams, the docs agents read updated), autogrills it and runs it to its automatic landing; then the next unit. `/fix-loc next` shows what would start next. Built on hal2 (`hal2-cli-agents`, `hal2-cli-git`). |
| [mfm](./skills/mfm/SKILL.md) | merge-from-main for any repository: merges the latest default branch (main, master, ...) into the current git worktree via `hal2-cli-git`, runs the repo's setup tasks (`setup` verb scripts, `.hal/hooks.toml`) and `.hal/hooks/merge-from-main/post-merge.sh`, resolves conflicts and fixes a failing setup or hook itself. |
| [mtm](./skills/mtm/SKILL.md) | merge-to-main for any repository, so several worktrees can work in parallel: commits all work (gitignores junk, never commits secrets, asks about unclear files), then lands the worktree through `hal2-cli-git`: with `.github/workflows/land.yml` through GitHub Actions (the candidate on `land/<slot>` with its pull request, fast-forwarded once green; a red job read, reproduced with `gate/main.sh <job>`, fixed and landed again until merged), elsewhere as one local merge commit after the repo's local gates; resets the worktree and deletes its build artifacts (cleanup, `.hal/cleanup`); resolves conflicts and fixes failures itself. |
| [adapt-merge-queue](./skills/adapt-merge-queue/SKILL.md) | Change the merge queue's priorities: `/adapt-merge-queue 12 18 15` makes these slots land first in this order and reserves their places (the queue waits at the front for a listed slot that is not done yet); hal2 owns the order (`hal2-cli-git worktree queue order`), the skill tells every affected session its place. `clear` drops it. |
| [create-worktree-session](./skills/create-worktree-session/SKILL.md) | Start a new agent session (Claude by default) in the repository's first free, clean worktree slot (the first from 01 with no session running and no work: no plan, no uncommitted changes, nothing unmerged into main; the worktree is created when missing), detached in a hal2 terminal host or a tmux window, its first prompt `/mfm` and then an optional task (`/create-worktree-session /shoot 13`); reports the slot, the attach command (in the clipboard) and the slots skipped for their work. Built on hal2 (`hal2-cli-git worktree run`). |
| [delete-worktree-session](./skills/delete-worktree-session/SKILL.md) | The opposite: stop a running agent session by slot or pane (`/delete-worktree-session 03`): by signal through `hal2-cli-agents stop`, never a typed `/exit`; the worktree and its work stay. Refuses its own session, a busy agent, a draft, running background tasks and a running landing unless confirmed; without an argument it lists the sessions and asks. Built on hal2 (`hal2-cli-agents`). |
| [list-free-worktrees](./skills/list-free-worktrees/SKILL.md) | List the repository's free worktrees: an agent session runs there but does no work and holds none (no agent busy, `plans/CURRENT_PLAN` names nothing, no uncommitted changes, nothing unmerged into main, no landing queued), with pane, state and how far behind main; `--all` says why each other slot is not free. Read-only, built on hal2. |
| [shoot](./skills/shoot/SKILL.md) | Pick the next shot from the agent CLI instead of Neovim: lists the open shots of the repo's `shotfiles/` via `hal2-cli-shooter shots list-open` as a table (id, shotfile, shot number, title), the 10 most important by default, all with `-a`, one shotfile with `/shoot <shotfile>`; the picked shot (or `/shoot <id>`) is marked sent in its shotfile and carried out in the session, like `<space>00` in hal2-nvim; from the main checkout it first asks where: a new worktree session per shot, a free one, or here. |
| [create-shot](./skills/create-shot/SKILL.md) | Write a new shot from the agent CLI instead of Neovim, the counterpart of `shoot`: `/create-shot tell: add reddit as a source` (or `/create-shot` alone for what the conversation just settled) picks the shotfile (the repo's, another repo's with `hal2:<shotfile>`, a global one with `global:<name>`, a new one when nothing fits), drafts a short title, keeps your words as the body and writes `## shot <n> <title>` with `hal2-cli-shooter shots create`, as hal2-nvim does; reports the shotfile, number and the id to `/shoot` it with. Then offers to implement it at once: in the next idle worktree session (running, no plan, nothing unmerged), or in a new worktree session when there is none. Asks only when the shotfile is unclear or an open shot asks the same; `--dry-run` writes nothing, `--implement` sends it without asking, `--no-implement` only writes it. |
| [digest-todolist-picture](./skills/digest-todolist-picture/SKILL.md) | Turn a photo of a handwritten to-do list (sent from the Claude iOS or Android app) into shots: reads every item, routes each to the right shotfile (the repo's, the global ones or another repo's), then walks you through the list top to bottom as written on paper, one item per plain-text message you can answer by voice (the handwritten text, unclear points, the exact shot `## shot <n> <title>` with body, shotfile and number), and writes each one you confirm right away with `hal2-cli-shooter shots create` (or the same format by hand in a cloud session). Ticked items are skipped, duplicates of open shots flagged; `--dry-run` writes nothing. |
| [tell](./skills/tell/SKILL.md) | Summarize anything from a URL or a path into `~/skills/tell/`: a video, playlist or channel (YouTube, TikTok, X, podcasts, any yt-dlp site; captions or local Whisper, background download), a web page (trafilatura + defuddle, Jina and Wayback fallbacks), a GitHub repo, issue, PR or discussion (`--deep` packs the repo with repomix), an X post or thread with its replies and video, a Hacker News thread or a Reddit post (article + discussion; Reddit falls back to an app token or the Arctic Shift archive when it blocks anonymous requests), or a document (PDF, DOCX, PPTX, EPUB, … via markitdown). A topic instead of a link (`/tell okf`) searches YouTube, the web, GitHub, Hacker News and your local documents for it, summarizes the relevant finds and writes a digest in `topics/<topic>/`. Several inputs at once get a digest. Every summary links back into its source (timestamps, paragraphs, line numbers, permalinks, pages), checks its quotes and links, lists related items, and gets a page in a browsable library with a source filter and a read-aloud button (local Supertonic-3 text-to-speech). Modes tldr/summary/chapters/detailed/wisdom/qa. Each source checks its own tools: run `scripts/<source>/install-prerequisites.sh` (or `scripts/install-prerequisites.sh` for all). |

## Shortcuts

| Shortcut | Runs |
|---|---|
| `/h` | `/handoff` |
| `/c` | `/handoff continue` |

A shortcut is a tiny generated skill (`skills/<shortcut>/SKILL.md`) that hands over to its skill, with any
arguments appended; only typing it runs it, the model never picks it on its own. To add one, put it in
[`aliases.json`](./aliases.json) (`{"c": {"skill": "handoff", "args": "continue"}}`) and run
`python3 scripts/gen-aliases.py`; `scripts/check-plugins.py` fails while the generated skills are out of date.

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

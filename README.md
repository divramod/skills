# divramod/skills

Agent skills by [divramod](https://github.com/divramod). They work in **Claude Code**, **Codex**, **Grok Build**, **OpenCode**
and every other harness that reads the [Agent Skills](https://agentskills.io) `SKILL.md` format.

## Skills

| Skill | What it does |
|---|---|
| [handoff](./skills/handoff/SKILL.md) | Hand off before `/clear` without losing context: records every decision from the conversation in the repo's intent doc (`docs/intent.md`), then rewrites `docs/handoff.md` with the goal, a link to the plan (`CURRENT_PLAN` or a plan file) and its current step, what is done, the next tasks with a done-when check, traps, open decisions and the prompt to start with; commits only those docs. `/handoff continue` reads it back and carries on. |
| [tell](./skills/tell/SKILL.md) | Summarize anything from a URL or a path into `~/skills/tell/`: a video, playlist or channel (YouTube, TikTok, X, podcasts, any yt-dlp site; captions or local Whisper, background download), a web page (trafilatura + defuddle, Jina and Wayback fallbacks), a GitHub repo, issue, PR or discussion (`--deep` packs the repo with repomix), an X post or thread with its replies and video, a Hacker News thread or a Reddit post (article + discussion; Reddit falls back to an app token or the Arctic Shift archive when it blocks anonymous requests), or a document (PDF, DOCX, PPTX, EPUB, … via markitdown). Several inputs at once get a digest. Every summary links back into its source (timestamps, paragraphs, line numbers, permalinks, pages), checks its quotes and links, lists related items, and gets a page in a browsable library with a source filter. Modes tldr/summary/chapters/detailed/wisdom/qa. Each source checks its own tools: run `scripts/<source>/install-prerequisites.sh` (or `scripts/install-prerequisites.sh` for all). |

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

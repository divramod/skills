# divramod/skills

Agent skills by [divramod](https://github.com/divramod). They work in **Claude Code**, **Codex**, **Grok Build**, **OpenCode**
and every other harness that reads the [Agent Skills](https://agentskills.io) `SKILL.md` format.

## Skills

| Skill | What it does |
|---|---|
| [dm-summarize-video](./skills/dm-summarize-video/SKILL.md) | Summarize a video, playlist or channel from a URL (YouTube, TikTok, X, podcasts, …) into `~/me/summaries/videos/`: captions via yt-dlp, local Whisper fallback, optional download (`-d`) and keyframes, modes tldr/summary/chapters/detailed/wisdom/qa. Needs yt-dlp, ffmpeg, uv: run its `scripts/install-prerequisites.sh`. |

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

---
name: public-skills-repos
description: Survey of the top 10 public GitHub agent-skills repos (Sep 2026) — obra/superpowers and mattpocock/skills lead; small, opinionated, dual-installable (plugin + npx skills) repos win.
status: in_progress
scope: global
created: 2026-09-24
---

# Research: public-skills-repos

## Question

We want to publish `divramod/skills` as a public skills repo in the spirit of
[mattpocock/skills](https://github.com/mattpocock/skills). What is the state of
the art in public GitHub skills repos — which are the top 10 by popularity, and
what does each do well / badly — so we can pick a structure, scope and
distribution model?

## TL;DR

- The market has consolidated on the **Agent Skills spec** (`skills/<name>/SKILL.md`,
  [agentskills.io](https://agentskills.io)) and two install channels: a **Claude Code
  plugin marketplace** (`.claude-plugin/marketplace.json`) and **`npx skills add <owner>/<repo>`**
  (vercel-labs/skills). Every top-10 repo supports at least one; the best support both.
- The two most-starred repos (obra/superpowers, mattpocock/skills) are **small (15–38 skills),
  opinionated, personal methodologies** — not mega-catalogs. Curation and a clear point of view beat volume.
- Mega-libraries (ECC ~900, alirezarezvani ~850 SKILL.md) get stars but pay for it in
  discoverability, quality variance, and README sprawl.

## Findings

Snapshot: GitHub API, 2026-09-24. Scope: **repos whose primary product is a collection
of skills**. Excluded (listed at the end): awesome-lists, apps/harnesses that merely use
skills, and single-skill viral repos.

| # | Repo | ★ | SKILL.md | License | Install channels |
|---|------|---|---------:|---------|------------------|
| 1 | [obra/superpowers](https://github.com/obra/superpowers) | 291k | 15 | MIT | Plugin (official + own marketplace), 12+ agents |
| 2 | [mattpocock/skills](https://github.com/mattpocock/skills) | 269k | 38 | MIT | Plugin + `npx skills` |
| 3 | [affaan-m/ECC](https://github.com/affaan-m/ECC) | 266k | ~903 | MIT | Plugin, npm, guided setup, ~15 agent dirs |
| 4 | [anthropics/skills](https://github.com/anthropics/skills) | 178k | 20 | mixed (Apache-2.0 + source-available) | Plugin marketplace |
| 5 | [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | 99k | 25 | MIT | Plugin + `npx skills` + clone |
| 6 | [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills) | 51k | 50 | MIT | Plugin + `npx skillkit` + clone |
| 7 | [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) | 49k | 6 | MIT | Plugin + `npx skills` + manual |
| 8 | [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) | 46k | 166 | MIT | `npx skills` + clone |
| 9 | [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills) | 31k | 9 | none declared | `npx skills` |
| 10 | [phuryn/pm-skills](https://github.com/phuryn/pm-skills) | 27k | 69 | MIT | 9 plugins in one marketplace |

Honourable mentions: [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) (26k, ~850 SKILL.md, 13 agents),
[google/skills](https://github.com/google/skills) (20k, 152 skills, Apache-2.0).

### 1. obra/superpowers — "an agentic skills framework & SDLC methodology"
A complete dev methodology (brainstorm → plan → subagent-driven dev → TDD → review)
made of ~15 composable skills plus bootstrap instructions that force the agent to use them.
- **Strengths:** strong point of view; skills designed to chain; in the official Claude
  plugin marketplace; broadest agent coverage (Claude, Codex, Cursor, Gemini, Copilot,
  Kimi, OpenCode, Devin, …) via per-agent plugin dirs; release notes + version-bump tooling.
- **Weaknesses:** heavyweight — it "owns the process" (exactly what mattpocock critiques);
  a dozen `.<agent>-plugin` dirs at the root add maintenance cost; commercial-services upsell.

### 2. mattpocock/skills — "Skills for Real Engineers"
Matt's daily-driver `.agents` skills, grouped `skills/{engineering,productivity,misc,in-progress,deprecated}`.
- **Strengths:** small, hackable, composable, model-agnostic; excellent README framing
  ("why these skills exist" as 4 concrete failure modes); explicit **two install
  philosophies** (plugin = subscribe/read-only, `npx skills` = fork/edit); a
  `/setup-matt-pocock-skills` onboarding skill; engineering hygiene — changesets +
  CHANGELOG, release workflow, `.agents/adr/`, `.out-of-scope/` for rejected ideas,
  `in-progress/` + `deprecated/` lifecycle buckets, `scripts/link-skills.sh` for local dev.
- **Weaknesses:** tied to one person's taste; no evals/tests for skill behavior;
  newsletter-funnel framing; no topics/tags set on the repo.

### 3. affaan-m/ECC — "agent harness performance optimization system"
A huge harness: skills, "instincts", memory, security, hooks, MCP config, for ~15 agents.
- **Strengths:** maximal coverage; npm distribution; security posture (gitleaks, official-source warning);
  guided installer.
- **Weaknesses:** ~900 skills + 2,000-line README — hard to audit or understand what
  you're installing; many root dotdirs; commercial Pro tier; high blast radius for
  a single install.

### 4. anthropics/skills — the reference implementation
Anthropic's example + document skills (docx/pdf/pptx/xlsx), plus `spec/` and `template/`.
- **Strengths:** canonical format and spec; `template/` skill to copy; production-grade
  document skills; official marketplace.
- **Weaknesses:** "demonstration and educational purposes" disclaimer; mixed licensing
  (doc skills are source-available, not OSS); not a coherent workflow — a showcase.

### 5. addyosmani/agent-skills — "production-grade engineering skills"
25 skills mapped to a lifecycle (DEFINE → PLAN → BUILD → VERIFY → REVIEW → SHIP) with
9 slash commands (`/spec`, `/plan`, `/build`, `/test`, `/review`, `/ship`).
- **Strengths:** clear lifecycle diagram in the README; commands + skills + agents + hooks;
  has an `evals/` folder; multi-agent plugin dirs; `npx skills` + marketplace.
- **Weaknesses:** overlaps heavily with superpowers/mattpocock; more ceremony than mattpocock;
  per-agent plugin dirs to maintain.

### 6. coreyhaines31/marketingskills — marketing for technical founders
~50 skills (CRO, copywriting, SEO, analytics), all anchored on a `product-marketing` context skill.
- **Strengths:** proves the model outside engineering; shared-context skill that other
  skills read first; `validate-skills.sh` (incl. official-spec validation); VERSIONS.md.
- **Weaknesses:** sponsored "Verified Partners" block + agency referral links in the
  README; uses `skillkit` rather than the more common `npx skills`.

### 7. kepano/obsidian-skills — product-scoped, tiny
6 skills teaching agents Obsidian's CLI, Markdown, Bases, JSON Canvas.
- **Strengths:** minimal, focused, 57-line README; spec-compliant; 3 install paths;
  authored by the product's own maker → authoritative.
- **Weaknesses:** narrow by design; little tooling/tests; only useful to Obsidian users.

### 8. K-Dense-AI/scientific-agent-skills — domain library for science
166 skills across bioinformatics, cheminformatics, clinical, imaging.
- **Strengths:** deep domain coverage; Python `tests/` + `scan_skills.py` security
  scanning of PR'd skills; CITATION.cff + arXiv paper; renamed to be agent-agnostic.
- **Weaknesses:** very long README (~970 lines) dominated by product/webinar promos;
  breadth makes quality uneven and skill discovery hard.

### 9. vercel-labs/agent-skills — official vendor skills
9 skills (vercel-optimize, react-best-practices, …); ships from the same org as the
`npx skills` CLI ([vercel-labs/skills](https://github.com/vercel-labs/skills)).
- **Strengths:** per-skill "Use when:" bullets in README are a great discovery pattern;
  `skills.sh.json` manifest; `packages/` for bundled tooling.
- **Weaknesses:** no license declared; no Claude plugin marketplace; vendor-centric.

### 10. phuryn/pm-skills — PM "operating system"
69 skills + 42 chained workflows split into **9 installable plugins** (discovery,
strategy, execution, GTM, …).
- **Strengths:** good granularity — users install only the plugin they need; commands
  chain skills into end-to-end flows; `validate_plugins.py` + tests; frameworks attributed
  (Torres, Cagan, Savoia).
- **Weaknesses:** 9 plugins × manifests to keep in sync; Claude/Cowork-first, other
  agents second-class.

### Cross-cutting patterns (what "good" looks like in 2026)

1. **Layout:** `skills/<category>/<skill>/SKILL.md` (+ optional `references/`, `scripts/`).
2. **Distribution:** `.claude-plugin/{plugin,marketplace}.json` **and** `npx skills add owner/repo`.
3. **README:** why-it-exists → 30-second install → catalog with a one-line "use when" per skill.
4. **Lifecycle:** `in-progress/` and `deprecated/` buckets; changesets/CHANGELOG; version sync script.
5. **Quality gates:** spec validation script, CI; evals are rare (addyosmani, K-Dense) — a differentiator.
6. **Licensing:** MIT is the default; missing licenses (vercel-labs) are a real adoption blocker.

### Excluded (not skill-collection repos)

- Awesome-lists: ComposioHQ/awesome-claude-skills (76k), hesreallyhim/awesome-claude-code (55k),
  VoltAgent/awesome-agent-skills (35k), travisvn/awesome-claude-skills (15k).
- Apps/harnesses: Shubhamsaboo/awesome-llm-apps, nexu-io/open-design, CherryHQ/cherry-studio, LibreChat.
- Single-skill viral repos: DietrichGebert/ponytail (145k), JuliusBrussee/caveman (108k),
  tt-a1i/archify (71k), mvanhorn/last30days-skill (63k), blader/humanizer (52k).
- Tooling/spec: vercel-labs/skills (`npx skills` CLI, 32k), agentskills/agentskills (spec, 26k).

## Recommendation

Model `divramod/skills` on **mattpocock/skills' structure**, borrowing select patterns:

1. `skills/<category>/<name>/SKILL.md`, spec-compliant frontmatter; `in-progress/` + `deprecated/` buckets.
2. Ship **both** `.claude-plugin/{plugin,marketplace}.json` and `npx skills` compatibility;
   explain the subscribe-vs-fork choice in the README (mattpocock).
3. README: short "why", 30-second install, catalog with "use when" bullets (vercel-labs).
4. Add a `validate-skills` script + GitHub Action checking frontmatter against the spec
   (marketingskills/pm-skills) — cheap and uncommon.
5. MIT license, CHANGELOG via changesets, `.agents/adr/` for decisions.
6. Stay **small and curated**; avoid per-agent dotdir sprawl — rely on the Agent Skills
   spec + `npx skills` for non-Claude agents.
7. Differentiator to consider: lightweight evals per skill (only ~2 of the top 10 have them).

## Open Questions

- Which skills to publish first — a subset of the existing `hal-*` skills (would need de-hal-ifying), or new general ones?
- One plugin vs. several category plugins (pm-skills model)?
- Keep the `hal-` prefix, or use neutral names for a public audience?

## Sources

- GitHub REST API (`gh search repos`, `gh api repos/...`), 2026-09-24 — star counts, trees, licenses, READMEs.
- [mattpocock/skills](https://github.com/mattpocock/skills) — reference repo; layout, manifest, README structure.
- [agentskills.io](https://agentskills.io) — the Agent Skills spec most repos target.
- [vercel-labs/skills](https://github.com/vercel-labs/skills) — `npx skills` installer used by 7/10 repos.
- Each repo linked in the table above — README + tree inspected.

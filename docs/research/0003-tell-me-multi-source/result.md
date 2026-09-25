---
name: tell-me-multi-source
description: How to generalize tell-me from videos to blog posts, GitHub repos, X posts, Hacker News threads and local documents — skill layout, extractors per source, adapter architecture, discussion summarization (Sep 2026).
status: done
scope: global
created: 2026-09-25
---

# Research: tell-me multi-source

## Question

tell-me summarizes videos (yt-dlp captions → agent → summary.md/html). How do we generalize it to blog posts,
GitHub repos, x.com posts, Hacker News posts and local documents, and which tools should each source use?

## TL;DR

- **Layout:** keep SKILL.md short (<500 lines) and route to one file per source, linked **directly** from SKILL.md
  (one level deep); the Anthropic `mcp-builder` skill does this with `reference/node_mcp_server.md` /
  `reference/python_mcp_server.md`. Deterministic work goes in scripts.
- **Don't nest files named `SKILL.md`/`skill.md`.** Claude Code reads only the top one, but the `npx skills`
  installer searches recursively when it finds no standard location, and macOS filesystems are case-insensitive.
  Use a different file name for subskills.
- **Architecture (llm fragments, steipete/summarize, Fabric, Obsidian Web Clipper):** route the URL by pattern to
  an adapter → every adapter writes the same normalized pair (content markdown + metadata.json with shared fields)
  → one shared summarization step with shared modes → source-specific guidance only where it differs.
- **Extractors (defaults first):**

| Source | Default | Fallback |
|---|---|---|
| web article | trafilatura 2.2 (`--markdown --with-metadata`) | Jina Reader `r.jina.ai/<url>` (renders JS, 20 req/min without a key) → Wayback `archive.org/wayback/available` |
| GitHub repo | `gh api repos/{o}/{r}` + `/readme` `/languages` `/releases/latest` `/topics` | unauthenticated REST (60/h); whole repo only on request: `npx repomix --remote <url> --compress` or gitingest |
| X post / thread | FxTwitter API v2: `/2/status/{id}`, `/2/thread/{id}` (author's thread, unrolled), `/2/conversation/{id}` (replies) | `cdn.syndication.twimg.com/tweet-result` (single post); video via yt-dlp. Nitter is dead (C&D Aug 2026) |
| Hacker News | Algolia `hn.algolia.com/api/v1/items/<id>` (whole comment tree in one call) | Firebase `hacker-news.firebaseio.com/v0/item/<id>.json` (one call per comment) |
| local document | MarkItDown 0.1.8 (`uvx 'markitdown[all]'`: pdf, docx, pptx, xlsx, epub, html, images) | `pdftotext -layout` (poppler); docling opt-in for hard PDFs/tables |

- **Discussions (HN, X replies):** Simon Willison's prompt works well: themes as headers, direct quotes with
  author attribution, a section for uncommon opinions. Quotes make the summary checkable (a script can grep each
  quote against the content file). Summarize the linked article first, then the discussion.

## Sources

- Anthropic skill best practices: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- Agent Skills spec: https://agentskills.io/specification
- anthropics/skills mcp-builder: https://github.com/anthropics/skills/tree/main/skills/mcp-builder
- Claude Code skills: https://code.claude.com/docs/en/skills · recursive discovery issue: https://github.com/anthropics/claude-code/issues/28266
- Vercel skills installer: https://github.com/vercel-labs/skills
- trafilatura: https://trafilatura.readthedocs.io/en/latest/usage-cli.html · eval: https://trafilatura.readthedocs.io/en/latest/evaluation.html
- defuddle: https://github.com/kepano/defuddle · Jina Reader: https://jina.ai/reader/
- repomix: https://github.com/yamadashy/repomix · gitingest: https://github.com/coderamp-labs/gitingest
- FxTwitter API: https://docs.fxembed.com/api/introduction · syndication: https://shkspr.mobi/blog/2025/04/you-dont-need-an-api-key-to-archive-twitter-data/
- HN API guide: https://cotera.co/articles/hacker-news-api-guide
- MarkItDown vs docling vs marker: https://www.danilchenko.dev/posts/markitdown-vs-docling-vs-marker/
- llm fragments: https://llm.datasette.io/en/stable/fragments.html · steipete/summarize: https://github.com/steipete/summarize
- Fabric: https://github.com/danielmiessler/Fabric · Obsidian Web Clipper templates: https://obsidian.md/help/web-clipper/templates
- HN themes prompt: https://til.simonwillison.net/llms/claude-hacker-news-themes

## Unverified

Marker license change; long-term availability of Jina Reader (Elastic acquisition) and FxTwitter (unofficial);
whether the `npx skills` installer matches a lowercase nested `skill.md`; the third-party benchmark numbers.

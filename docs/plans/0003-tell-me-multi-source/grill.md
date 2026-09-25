# Grill — 0003-tell-me-multi-source (spec) — 2026-09-25

| # | Branch | Question | Answer |
|---|---|---|---|
| 1 | Layout | Name of the per-source instruction file | `SUBSKILL.md` (a nested `skill.md` would be picked up as a separate skill) |
| 2 | Prereqs | Where the prereq scripts live | per source + top-level aggregator |
| 3 | Library | Disk layout | `~/me/summaries/<kind>/…`, videos unchanged |
| 4 | HN | Article + discussion shape | one summary, two parts |
| 5 | X | Default scope | thread + replies always |
| 6 | X | Video in a post | transcript automatically, **and the video is downloaded automatically** |
| 7 | GitHub | Default depth | API + README; `--deep` = repomix |
| 8 | File | Keep the original? | copy into the folder (sha256 dedupe) |
| 9 | Web | Extractor chain | "the highest quality one": trafilatura + defuddle, best wins; Jina → Wayback fallback |
| 10 | Contract | Content file name | `content.md` everywhere (migrate existing videos) |
| 11 | Phasing | Order | restructure first, then one phase per source |
| 12 | Scope | Extras | check_quotes, related items, multiple inputs, GitHub issues/PRs/discussions — all in |

Also decided by the user before the grill: `platforms/` becomes `subskills/`; `subskills/`, `templates/` and
`scripts/` each get a `shared/` folder.

---
name: tell-me-multi-source-context
description: Files, patterns and gotchas for implementing the tell-me multi-source plan.
---

## Files to Load

- `skills/tell-me/SKILL.md`: the current video flow. It becomes the router.
- `skills/tell-me/scripts/_common.py`: `require()`, `run_main()`, `library_root()`, `write_json`, `detect_agent`.
- `skills/tell-me/scripts/{prepare_video,save_summary,render_html,library,serve_library,check_links,link_dates}.py`
- `skills/tell-me/templates/*.md`
- `scripts/check-plugins.py`, `CLAUDE.md`, `AGENTS.md` (the skill script rules)
- `research/0003-tell-me-multi-source/research.md`: API endpoints and extractor choices

## Patterns

- Scripts are stdlib Python and use `argparse(description=__doc__)` and `run_main(main)`. Exit codes: 1 for an expected error, 2 for a missing tool. JSON goes to stdout; progress goes to stderr via `log()`.
- **Flat imports** (`from _common import …`). After the move, every script outside `shared/` starts with
  `sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))`.
- Shared code never imports a source module. It calls source scripts as subprocesses (e.g. `serve_library.py`'s download button calls `scripts/video/download_video.py`).
- Tests: `test_<module>.py` sits next to its module. Run them per folder:
  `for d in */; do python3 -m unittest discover -s "$d" -p 'test_*.py' || exit 1; done` (no `__init__.py` needed).
- Network in tests is forbidden. Put recorded JSON/HTML fixtures under `scripts/<s>/fixtures/`.
- `metadata.json` is written atomically (`write_json`) because background video downloads write it concurrently.

## Gotchas

- The spec's success-criteria command `unittest discover -s . -t .` does not find tests in subfolders unless they have `__init__.py`. Use the per-folder loop above. Phase 001 updates the spec criterion.
- `library.js` moves from `~/me/summaries/videos/` to `~/me/summaries/`. Old pages reference the sidebar script relative to the root, so after the move run `library.py --pages` to re-render them.
- `DM_SUMMARIZE_VIDEO_ROOT` pointed at the videos root; the new `TELL_ME_ROOT` points at `~/me/summaries`. When only the old variable is set, root = its parent.
- macOS filesystems are case-insensitive, so never create `skill.md` under `subskills/`.
- `check-plugins.py` currently requires `scripts/check-prerequisites.sh` at the top level. Keep it there (as the aggregator) and add the per-folder rule.
- FxTwitter and Jina are unofficial or third-party: always print which endpoint failed and which fallback ran.

## Links

- Spec: [spec.md](spec.md) · Grill: [grill.md](grill.md)
- Anthropic skill best practices: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- FxTwitter API: https://docs.fxembed.com/api/introduction · Algolia HN: https://hn.algolia.com/api
- trafilatura: https://trafilatura.readthedocs.io · defuddle: https://github.com/kepano/defuddle · repomix: https://github.com/yamadashy/repomix · markitdown: https://github.com/microsoft/markitdown

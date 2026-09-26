---
name: restructure-and-contract-context
description: Context for phase 001 (restructure-and-contract).
---

## Files to Load

- skills/tell-me/** (all), scripts/check-plugins.py, CLAUDE.md, AGENTS.md
- ../../context.md (patterns, gotchas), ../../spec.md (contract, decisions)

## Patterns

See the masterplan context: stdlib scripts, `run_main`, sys.path bootstrap to `scripts/shared`, fixtures without network, tests per folder.

## Gotchas

Import breakage after `git mv`, and the shared→video coupling in serve_library. Old pages keep pointing at the old library.js until they are re-rendered.

## Links

- [spec](../../spec.md) · [masterplan](../../plan.md) · [research](../../../../research/0003-tell-me-multi-source/research.md)

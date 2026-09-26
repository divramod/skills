---
name: hn-source-context
description: Context for phase 003 (hn-source).
---

## Files to Load

- skills/tell-me/{scripts,subskills,templates}/hn/, scripts/shared/check_quotes.py, subskills/shared/discussion.md
- ../../context.md (patterns, gotchas), ../../spec.md (contract, decisions)

## Patterns

See the masterplan context: stdlib scripts, `run_main`, sys.path bootstrap to `scripts/shared`, fixtures without network, tests per folder.

## Gotchas

Algolia lags minutes behind for brand-new items (Firebase fallback); very large threads (>1000 comments) are expensive in tokens.

## Links

- [spec](../../spec.md) · [masterplan](../../plan.md) · [research](../../../../research/0003-tell-me-multi-source/research.md)

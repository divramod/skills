---
name: github-source-context
description: Context for phase 004 (github-source).
---

## Files to Load

- skills/tell-me/{scripts,subskills,templates}/github/
- ../../context.md (patterns, gotchas), ../../spec.md (contract, decisions)

## Patterns

See the masterplan context: stdlib scripts, `run_main`, sys.path bootstrap to `scripts/shared`, fixtures without network, tests per folder.

## Gotchas

Unauthenticated rate limit; big monorepos (budget + --deep warning); GraphQL is needed for discussions (gh only).

## Links

- [spec](../../spec.md) · [masterplan](../../masterplan.md) · [research](../../../../research/0003-tell-me-multi-source/result.md)

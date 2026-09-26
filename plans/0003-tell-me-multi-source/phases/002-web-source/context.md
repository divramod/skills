---
name: web-source-context
description: Context for phase 002 (web-source).
---

## Files to Load

- skills/tell-me/{scripts,subskills,templates}/web/
- ../../context.md (patterns, gotchas), ../../spec.md (contract, decisions)

## Patterns

See the masterplan context: stdlib scripts, `run_main`, sys.path bootstrap to `scripts/shared`, fixtures without network, tests per folder.

## Gotchas

defuddle calls itself a work in progress; Jina rate limit (20/min); text fragments are not supported in Firefox before v131 (links still open the page).

## Links

- [spec](../../spec.md) · [masterplan](../../masterplan.md) · [research](../../../../research/0003-tell-me-multi-source/result.md)

---
name: x-source-context
description: Context for phase 005 (x-source).
---

## Files to Load

- skills/tell-me/{scripts,subskills,templates}/x/
- ../../context.md (patterns, gotchas), ../../spec.md (contract, decisions)

## Patterns

See the masterplan context: stdlib scripts, `run_main`, sys.path bootstrap to `scripts/shared`, fixtures without network, tests per folder.

## Gotchas

FxTwitter is unofficial and can break or rate-limit; protected accounts are unreachable (clear error).

## Links

- [spec](../../spec.md) · [masterplan](../../masterplan.md) · [research](../../../../research/0003-tell-me-multi-source/result.md)

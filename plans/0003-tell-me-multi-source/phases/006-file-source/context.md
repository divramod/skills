---
name: file-source-context
description: Context for phase 006 (file-source).
---

## Files to Load

- skills/tell-me/{scripts,subskills,templates}/file/
- ../../context.md (patterns, gotchas), ../../spec.md (contract, decisions)

## Patterns

See the masterplan context: stdlib scripts, `run_main`, sys.path bootstrap to `scripts/shared`, fixtures without network, tests per folder.

## Gotchas

markitdown is weak on multi-column PDFs and tables (docling is the future opt-in); large files (size warning > 50 MB).

## Links

- [spec](../../spec.md) · [masterplan](../../plan.md) · [research](../../../../research/0003-tell-me-multi-source/research.md)

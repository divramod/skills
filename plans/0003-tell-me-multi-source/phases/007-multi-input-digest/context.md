---
name: multi-input-digest-context
description: Context for phase 007 (multi-input-digest).
---

## Files to Load

- skills/tell-me/scripts/shared/prepare.py, templates/shared/digest.md, SKILL.md
- ../../context.md (patterns, gotchas), ../../spec.md (contract, decisions)

## Patterns

See the masterplan context: stdlib scripts, `run_main`, sys.path bootstrap to `scripts/shared`, fixtures without network, tests per folder.

## Gotchas

Wave-02 overlap: edits `shared/prepare.py` and SKILL.md. Keep the diff small and rebase last in the wave.

## Links

- [spec](../../spec.md) · [masterplan](../../plan.md) · [research](../../../../research/0003-tell-me-multi-source/research.md)

# Deterministic first: whatever can be done by code is done by code

## Status

Accepted (2026-10-03, the user). Extends AGENTS.md's "Skill script rules".

## Context

Skills run in model sessions. Every step a model performs costs tokens and time, varies between runs and can be
misread. A loop skill pays for that on every tick. The owner skill read ~25k tokens per 15-minute round even when
nothing was wrong (plans/0007/analysis.md). Most of a skill's steps follow fixed rules: checking state,
classifying it by known patterns, choosing from a table, running a command, filling a text template, writing a log.

## Decision

1. **Everything that can be done deterministically is done deterministically**, in a skill's `scripts/` or in a CLI
   it calls. A model only does what needs judgment: reading free text written by people or agents, deciding between
   options no rule settles, writing prose that has no template, reviewing.
2. **Classify every step** of a new or changed skill: **D** (code does it), **T** (code decides, and the output is a
   fixed text or command), **J** (judgment). `SKILL.md` keeps only the J steps plus the calls to the D/T code.
3. **Loops and watchers run as code first.** A recurring skill gets an external timer (launchd, systemd, cron) for
   its deterministic tick. The model is woken only when the tick found judgment work, with only the instructions
   that work needs. A quiet tick costs no model call.
4. **Templates over prose.** Messages, briefs, log lines, summaries and reports that follow a pattern are rendered by
   code. The model adds free text only where the pattern has a slot for it.
5. **Small instruction files.** Instructions for rare J cases live in their own files, read when that case occurs,
   not in the always-loaded `SKILL.md`.
6. **Tests.** Deterministic parts get unit tests (`python3 -m unittest discover -s skills/<name>/scripts`), as the
   script rules already require.

## Consequences

- Existing skills move over when they are touched. The owner goes first (plan 0007), then sanity-watch, then
  fix-autoclear.
- A review of a skill change asks: "which of these model steps could be a script?"
- More code to maintain in exchange for cheaper, faster and reproducible runs. A rule that turns out to need
  judgment goes back to J, written down in the skill.

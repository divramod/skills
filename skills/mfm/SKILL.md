---
name: mfm
description: merge-from-main — merge the latest default branch (main, master, ...) into the current git worktree, in any repository and on any branch, then run the repo's `.hal/hooks/merge-from-main/post-merge.sh`; resolves merge conflicts and fixes a failing hook itself. Use when the user says /mfm, "merge from main", "update the worktree with main", or a prompt says to run merge-from-main before starting. `/mfm h` shows help.
---

# mfm

Brings the default branch into the current worktree. `hal2-cli-git` does the git work (fetch, stash around the
merge, the hook, the push); this skill does what needs judgment: conflicts, a failing hook and the report.
`S=<skill-dir>/scripts`. Ask every question with the question tool, recommended option first.

| Call | Does |
|---|---|
| `/mfm [<slot>]` | merge the default branch into the current worktree (or hal slot `<slot>`) |
| `/mfm h`, `/mfm help` | print this table and stop |

## Run

1. `hal2-cli-git worktree merge-from-main --json [<slot>]` from the worktree. If the command is missing or has no
   `--json`, run `bash $S/install-prerequisites.sh` once and retry.
2. Act on the exit code; after every fix go back to 1, so the hook and the push run too:

| Exit | JSON `status` | Do |
|---|---|---|
| 0 | `ok` | [report](#report) |
| 3 | `conflict` | [resolve](#conflicts) the listed `files`, commit, rerun |
| 4 | `hook_failed` | [fix the hook's cause](#failing-hook), commit, rerun |
| 1 | `error` | report the `message`, stop. On the default branch itself there is nothing to do: /mfm is for worktrees |

## Conflicts

For each conflicted file, understand both sides before editing: `git show :1:<f>` (base), `:2:<f>` (this
worktree), `:3:<f>` (the default branch), and `git log --oneline -3 <side> -- <f>` for why each side changed it.

- **Lockfiles and generated files**: take the default branch's version (`git checkout --theirs <f>`), then
  regenerate with the repo's own tool (`cargo check`, `bun install`, `npm install --package-lock-only`, ...).
- **Everything else**: keep both intents: combine independent additions, apply one side's rename or refactor to
  the other side's new code. No conflict markers may remain (`git diff --check`).
- **Contradicting intents** you cannot reconcile with confidence: show both sides in a few lines and ask
  (keep this worktree's, keep the default branch's, or your combined proposal).

`git add` the files, `git commit --no-edit`, rerun.

## Failing hook

The JSON names the `script`, its `exit_code` and the tail of its `output`. Fix the cause in this worktree (the
code, a test, a missing setup step), not the hook: change the hook only when the hook itself is wrong, and say
so. `left_changes: true` means the hook passed but changed files (formatting, generated code): review and commit
them. Commit each fix with a real message in the repo's style, then rerun.

Stop after **3 runs in a row that fail the same hook with the same error**: report what fails and what you tried.

## Report

One short block: merged from (`from`, whether it `changed`), `pushed`, the `hooks` that ran, conflicts resolved
(file and how), fixes committed (hash and subject).

Never touch the main checkout or other worktrees (the merge only changes this worktree), and never push anything
but this worktree's branch.

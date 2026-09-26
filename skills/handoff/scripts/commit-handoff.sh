#!/usr/bin/env bash
# Commit one handoff file and nothing else: other staged or unstaged changes stay as they are.
# Usage: commit-handoff.sh <file> [message]
# Exit 0: committed (or nothing to commit). Exit 1: usage or git error. Exit 2: git missing.
set -euo pipefail

if ! command -v git >/dev/null 2>&1; then
  echo "commit-handoff.sh: git is missing; run install-prerequisites.sh" >&2
  exit 2
fi

file="${1:-}"
message="${2:-docs: update handoff}"
if [[ -z "$file" ]]; then
  echo "usage: commit-handoff.sh <file> [message]" >&2
  exit 1
fi
if [[ ! -f "$file" ]]; then
  echo "commit-handoff.sh: $file does not exist" >&2
  exit 1
fi
git rev-parse --is-inside-work-tree >/dev/null

git add -- "$file"
if git diff --cached --quiet -- "$file"; then
  echo "nothing to commit: $file is unchanged"
  exit 0
fi
# With a pathspec, git commits only that path, whatever else is staged.
git commit --quiet -m "$message" -- "$file"
git log --oneline -1

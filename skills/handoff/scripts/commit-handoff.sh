#!/usr/bin/env bash
# Commit the named handoff docs and nothing else: other staged or unstaged changes stay as they are.
# Usage: commit-handoff.sh <message> <file> [file ...]
# Exit 0: committed (or nothing to commit). Exit 1: usage or git error. Exit 2: git missing.
set -euo pipefail

if ! command -v git >/dev/null 2>&1; then
  echo "commit-handoff.sh: git is missing; run install-prerequisites.sh" >&2
  exit 2
fi

if [[ $# -lt 2 ]]; then
  echo "usage: commit-handoff.sh <message> <file> [file ...]" >&2
  exit 1
fi
message="$1"
shift
for file in "$@"; do
  if [[ ! -e "$file" ]]; then
    echo "commit-handoff.sh: $file does not exist" >&2
    exit 1
  fi
done
git rev-parse --is-inside-work-tree >/dev/null

git add -- "$@"
if git diff --cached --quiet -- "$@"; then
  echo "nothing to commit: $* unchanged"
  exit 0
fi
# With pathspecs, git commits only those paths, whatever else is staged.
git commit --quiet -m "$message" -- "$@"
git log --oneline -1

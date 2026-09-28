#!/usr/bin/env bash
# Commit the named decision docs and keep HANDOFF.md out of git: the root
# HANDOFF.md is per-worktree session state, so it is gitignored (added to the
# root .gitignore when missing) and untracked (when a repo still tracks it),
# and those two changes go into the same commit. Nothing else is committed:
# other staged or unstaged changes stay as they are (the commit is built in a
# temporary index). Git hooks run as usual.
# Usage: commit-handoff.sh <message> [file ...]   (a HANDOFF.md among the files is skipped)
# Exit 0: committed (or nothing to commit). Exit 1: usage or git error. Exit 2: git missing.
set -euo pipefail

if ! command -v git >/dev/null 2>&1; then
  echo "commit-handoff.sh: git is missing; run install-prerequisites.sh" >&2
  exit 2
fi

if [[ $# -lt 1 ]]; then
  echo "usage: commit-handoff.sh <message> [file ...]" >&2
  exit 1
fi
message="$1"
shift
git rev-parse --is-inside-work-tree >/dev/null
root="$(git rev-parse --show-toplevel)"
handoff="$root/HANDOFF.md"

docs=()
for file in "$@"; do
  if [[ "$(cd "$(dirname "$file")" 2>/dev/null && pwd -P)/$(basename "$file")" == "$(cd "$root" && pwd -P)/HANDOFF.md" ]]; then
    continue
  fi
  if [[ ! -e "$file" ]]; then
    echo "commit-handoff.sh: $file does not exist" >&2
    exit 1
  fi
  docs+=("$file")
done

# Gitignore HANDOFF.md (by the rules, whether or not it is tracked).
if ! git check-ignore -q --no-index "$handoff"; then
  gitignore="$root/.gitignore"
  if [[ -s "$gitignore" && -n "$(tail -c1 "$gitignore")" ]]; then
    printf '\n' >>"$gitignore"
  fi
  printf '%s\n' "# This worktree's session state (/handoff), never committed" "HANDOFF.md" >>"$gitignore"
  echo "gitignored HANDOFF.md in $gitignore"
  docs+=("$gitignore")
fi

paths=("${docs[@]}")
tracked=false
if git ls-files --error-unmatch -- "$handoff" >/dev/null 2>&1 \
  || { git rev-parse -q --verify HEAD >/dev/null && git cat-file -e "HEAD:HANDOFF.md" 2>/dev/null; }; then
  tracked=true
  paths+=("$handoff")
fi
if [[ ${#paths[@]} -eq 0 ]]; then
  echo "nothing to commit: no docs named, HANDOFF.md already ignored and untracked"
  exit 0
fi

# The commit: HEAD plus exactly these changes, in an index of its own.
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
with_commit_index() { GIT_INDEX_FILE="$tmp/index" git "$@"; }
if git rev-parse -q --verify HEAD >/dev/null; then
  with_commit_index read-tree HEAD
else
  with_commit_index read-tree --empty
fi
if [[ ${#docs[@]} -gt 0 ]]; then
  with_commit_index add -- "${docs[@]}"
fi
if $tracked; then
  with_commit_index rm -q --cached --ignore-unmatch -- "$handoff"
fi
if git rev-parse -q --verify HEAD >/dev/null && with_commit_index diff --cached --quiet HEAD --; then
  echo "nothing to commit: ${docs[*]:-HANDOFF.md} unchanged"
  exit 0
fi
with_commit_index commit --quiet -m "$message"
# The real index follows the new commit for these paths only.
git reset -q -- "${paths[@]}"
if $tracked; then
  echo "untracked HANDOFF.md (it stays on disk)"
fi
git log --oneline -1

#!/usr/bin/env bash
# Check the tools /digest-todolist-picture's scripts use: git and python3 (required), hal2-cli-shooter (optional:
# without it shots.py writes the same shot format itself, and there are no global shotfiles).
missing=0
for tool in git python3; do
  if command -v "$tool" >/dev/null 2>&1; then
    echo "ok $tool"
  else
    echo "MISSING $tool -> brew install $tool (or apt-get install $tool)"
    missing=1
  fi
done
if command -v hal2-cli-shooter >/dev/null 2>&1 && hal2-cli-shooter --help | grep -q 'shots create'; then
  echo "ok hal2-cli-shooter"
else
  echo "MISSING hal2-cli-shooter (optional) -> cargo install --git https://github.com/divramod/hal2 hal2-cli-shooter"
fi
exit "$missing"

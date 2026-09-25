#!/usr/bin/env bash
# Run the unit tests of every scripts/<folder>/ that has any (each folder in its own interpreter: the folders share
# module names such as prepare.py). Exit 1 on the first failing folder.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
for d in "$HERE"/*/; do
  ls "$d"test_*.py >/dev/null 2>&1 || continue
  echo "== $(basename "$d")"
  python3 -m unittest discover -s "$d" -p 'test_*.py' || exit 1
done

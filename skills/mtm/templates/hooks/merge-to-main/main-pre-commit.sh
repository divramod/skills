#!/usr/bin/env bash
# managed by /mtm config: runs parts/*/main-pre-commit.sh (see lib.sh).
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
hal_run_parts main-pre-commit

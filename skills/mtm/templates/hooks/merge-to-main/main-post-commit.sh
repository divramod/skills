#!/usr/bin/env bash
# managed by /mtm config: runs parts/*/main-post-commit.sh (see lib.sh).
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
hal_run_parts main-post-commit

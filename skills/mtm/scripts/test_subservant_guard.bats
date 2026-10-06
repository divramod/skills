#!/usr/bin/env bats
# subservant-guard.sh: a slot with plans/LEAD never lands.

setup() {
  here="$BATS_TEST_DIRNAME"
  tmp="$(mktemp -d)"
  git init -q "$tmp/wt"
  mkdir -p "$tmp/wt/sub"
}

teardown() { rm -rf "$tmp"; }

@test "a worktree without the marker passes silently" {
  run bash "$here/subservant-guard.sh" "$tmp/wt"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "a marked slot is refused, naming the lead" {
  mkdir -p "$tmp/wt/plans" && echo "02 0005-big-plan 3" > "$tmp/wt/plans/LEAD"
  run bash "$here/subservant-guard.sh" "$tmp/wt/sub"
  [ "$status" -eq 1 ]
  [[ "$output" == *"subservant of slot 02 (plan 0005-big-plan step 3"* ]]
  [[ "$output" == *"plan.py report 3"* ]]
}

@test "the current directory is the default" {
  mkdir -p "$tmp/wt/plans" && echo "07 0001-x 9" > "$tmp/wt/plans/LEAD"
  cd "$tmp/wt/sub"
  run bash "$here/subservant-guard.sh"
  [ "$status" -eq 1 ]
  [[ "$output" == *"slot 07"* ]]
}

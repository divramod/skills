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

@test "a bare slot name resolves to the worktree of that folder name" {
  git -C "$tmp/wt" -c user.email=t@t -c user.name=t commit -q --allow-empty -m init
  git -C "$tmp/wt" worktree add -q -b 31 "$tmp/slots/31"
  mkdir -p "$tmp/slots/31/plans" && echo "30 0013-parallel 4" > "$tmp/slots/31/plans/LEAD"
  cd "$tmp/wt"
  run bash "$here/subservant-guard.sh" 31
  [ "$status" -eq 1 ]
  [[ "$output" == *"subservant of slot 30 (plan 0013-parallel step 4"* ]]
}

@test "a bare slot name without the marker passes, whatever the current worktree holds" {
  git -C "$tmp/wt" -c user.email=t@t -c user.name=t commit -q --allow-empty -m init
  git -C "$tmp/wt" worktree add -q -b 32 "$tmp/slots/32"
  mkdir -p "$tmp/wt/plans" && echo "07 0001-x 9" > "$tmp/wt/plans/LEAD"
  cd "$tmp/wt"
  run bash "$here/subservant-guard.sh" 32
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "an unknown slot name exits 3" {
  cd "$tmp/wt"
  run bash "$here/subservant-guard.sh" 99
  [ "$status" -eq 3 ]
  [[ "$output" == *"named '99'"* ]]
}

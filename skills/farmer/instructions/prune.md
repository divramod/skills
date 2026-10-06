# Woken for prune (prune)

The tick does the duty itself (`prune.py`, hal2 plan 0143): every round it checks each numbered slot 00-99 and
prunes the free ones; nothing of it needs you unless it failed. A slot is free when nothing in it is unsaved: no
commit (its branch or a side branch `NN-*`) that origin's default branch lacks, no change, no `plans/CURRENT_PLAN`,
no merge queue ticket or boss pause, no busy agent, no session active in the last 30 minutes (10-99), no build
running in it and no open question to the user. Main, the role slots (`farmer-<repo>`, ...) and other names are
never touched.

- **00-09**: `prune.py clean NN` deletes the build artifacts (the cleanup skill), once per landing (keyed on HEAD).
- **10-99**, one per round: `prune.py remove NN` types `/exit` into the idle session's empty prompt (a draft refuses
  it), kills it only when it does not exit (delete-worktree-session's `stop.py`), then runs
  `hal2-cli-git worktree remove NN --remote` (the local branch, and `origin/NN` once merged). The user allowed
  stopping any idle session there holding no work, also their own (2026-10-06, answer 2a).
- **Disk**: every 6 hours a log line with the free disk and the 5 biggest worktrees (in the round summary), a notice
  for the user under 100 GB free.

`python3 $S/prune.py scan` lists every slot and why it is not free. A `run` of the duty that failed (its exit in the
log) needs a look: read its output, run `prune.py scan`, and leave a slot that holds anything alone. Log what you
did: `python3 $S/mtm_scan.py record prune <slot> "<what you did>" --note "<why>"`. Never remove a slot by hand that
`prune.py` refuses, never `--force` a removal.

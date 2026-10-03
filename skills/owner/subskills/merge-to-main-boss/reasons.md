# Why a merge to main does not happen

The boss's case library. There is one case per cause, newest first. A recurrence adds a line under its case's
**Occurrences**. **Remedy** is what the boss does now. **Lasting fix** is the change in hal2 or a skill that stops
it for good: `none`, `shot <shotfile>/<n>`, `plan <NNNN>` or `landed <plan> <date>`.

The first eight cases come from the survey of 2026-10-03 07:30. Nothing had landed on hal2 main since 16:31 the day
before, while 5 landings were ready and waiting.

## R10 · The Docker engine stops starting containers mid-landing

- **Signature**: a `test-e2e` task sits at `Container ... Starting` with no output for minutes;
  `hal2-cli-docker-compose doctor --json` says `stuck` ("a container of <image> did not start within 20s"), while
  `docker ps` still answers and running containers stay up.
- **Cause**: Docker Desktop's engine wedges under load (research in docs/docker.md); the gate's `doctor --repair`
  ran before the task, so the landing does not notice until the task's timeout (15m).
- **Occurrences**:
  - 2026-10-03 11:09 · wt 15 (train B) · libs.hal2-n8n.test-e2e, n8n-postgres "Starting" since 10:59
  - 2026-10-03 11:24 · wt 15 rerun · n8n-n8n "Starting" since 11:14 (the gate's probe had passed); owner ran `doctor --repair` → ready
- **Remedy**: tell the holder it is the engine, not its code; let the task time out (or stop it), then rerun at
  once: the gates' `doctor --repair` restarts the engine. Never disable the test for it.
- **Lasting fix**: shot plugin-docker-compose/4 (a test-e2e probes the engine when no container starts and repairs
  once or fails fast). Waits for a free worker slot.

## R1 · A failed landing holds the queue while its agent sleeps

- **Signature**: `scan.py` finding `held-idle`. The queue head is `held`, reason `failed`, with no live landing
  process, and its agent is `sleeping` or `done`.
- **Cause**: the plan's landing rule says "notify and stop with the queue held" after repeated failures. Overnight
  nobody answers the notification, so the queue stays dead for hours. In this case wt 12 stopped at 02:40 after 7
  attempts and the queue stood still until 07:45.
- **Occurrences**:
  - 2026-10-03, hal2 wt 12 (plan 0114), 5 h dead. The failure was a load-sensitive timing test that was also red
    on main alone.
- **Remedy**: wake the holder by SendMessage. A test that fails on main too, or only under load, gets disabled
  (R2) and the holder reruns its landing. If the holder does not move within one round: `hal2-cli-git worktree
  release <slot>` frees the queue, and the holder requeues after its fix.
- **Lasting fix**: none. The idea is that the plan skill's landing rule asks the boss before it stops, not the
  sleeping user.

## R2 · Timing and latency-budget tests fail under load

- **Signature**: `flaky-candidate`. The message contains budget, watchdog, `< limit`, "busy machine", Elapsed or a
  timeout, the load per core is ≥ 2, and the test passes alone.
- **Known tests (hal2)**:
  - Hal2Kit: ConversationStressTests.everyPlaceAtOnceStaysResponsive (53 ms vs 50 ms; fails 2/3 on main at load
    5), ConversationAccessibilityTests.theGridReadWhileItGrowsIsCheap and theGridOfSixRealSizeAgentsIsCheap,
    WebHostTests.servesThePageAndRoundTripsMessagesAndCalls (10 s page load at load 160–190), iOS WebCanvasTests.
  - Rust: hal2-daemon budgets the_daemon_answers_within_its_budgets, git_budgets, hal2-hub-authz
    a_decision_takes_under_a_millisecond.
  - UI tests: AgentsNodesUITests waitForNode, GitNodesUITests.
- **Occurrences**:
  - 2026-10-01/02/03 in wt 01, 08, 09, 12, 13 and 14, many times.
- **Remedy**: the user's rule of 2026-10-03 is to disable it rather than retry. Mark it
  `.disabled("flaky under landing load <date>, merge-to-main-boss")` in Swift, or `#[ignore = "..."]` in Rust, in
  the branch that is landing (or directly in main), add an entry to the ledger `~/skills/merge-to-main-boss/<repo>/flaky.md`,
  and file one shot to make it load-proof and enable it again.
- **Lasting fix**: none. The idea is budgets scaled by load (the `testing::budgets` median idea, extended to
  Swift).

## R3 · The machine is overloaded while a landing runs

- **Signature**: `load-high`, with load 75–500 on 10 cores during a landing.
- **Cause**: other worktrees build, run `build.sh check`, run Docker cross-builds or resume benchmarks beside the
  landing's gates. That causes R2.
- **Occurrences**:
  - 2026-10-02 16:41 (wt 08, caused by wt 00's build and wt 10's Linux Docker build).
  - 2026-10-02 23:39–01:02 (wt 12, after the benchmark resume).
- **Remedy**: tell the busy slots to pause heavy work (the `pause` skill) until the landing ends, then let them
  continue.
- **Lasting fix**: none. The idea is a landing lock that every build script honours.

## R4 · Waiters lose their place: `reserve --max-wait 100m` outlives the shell's 2 h limit

- **Signature**: the same slot is re-enqueued with a new seq, and its agent reports "reserve killed by the 2 h
  limit".
- **Cause**: while the queue is held, `reserve --max-wait 100m` sometimes did not exit at 100 min. The harness
  killed it at 2 h and the ticket was gone. 60-minute slices exit on time. This may be a hal2-cli-git bug: the
  time limit is not checked while the held head is being settled or taken over.
- **Occurrences**:
  - 2026-10-03 wt 01, 02 (twice), 09, 10 and 15.
- **Remedy**: tell waiters to use `--max-wait 25m` slices.
- **Lasting fix**: none. File a shot for hal2-cli-git.

## R5 · Docker images are gone in the middle of a landing

- **Signature**: test-e2e fails while downloading images, or with a proxy timeout.
- **Cause**: another session ran `docker system prune -a`.
- **Occurrences**:
  - 2026-10-02 16:38, wt 08.
- **Remedy**: re-pull the images before rerunning. Ask sessions never to prune while a landing is active.
- **Lasting fix**: none.

## R6 · Finished work waits for the user, not the queue

- **Signature**: `work-not-queued`. The plan is at its last steps and the agent asked the user something.
- **Causes**:
  - UI tests need a free or unlocked Mac (wt 04, 05, 06, 14).
  - A product decision is open (wt 00: GitHub access for the launchd daemon; wt 07: the research decision).
  - An ordering rule ("04 waits for 0091 step 10").
  - The user said "stop merging" earlier (wt 08 waits for the user's own /mtm).
- **Remedy**: one batched push notification, or one question block when the user is present, with every open
  decision listed together. The boss never decides product questions. With the user's general "merge fast" rule
  it may tell a plan to land without UI tests that only failed for unrelated reasons, and run those tests after
  the landing.
- **Lasting fix**: none.

## R7 · Work without any agent session

- **Signature**: `work-without-agent`. A worktree has commits not on main and no agent.
- **Occurrences**:
  - 2026-10-03: wt 11 (plan 0085, 13 commits) and wt 13 (plan 0102, 7 commits; its last landing failed
    2026-10-02 03:54).
- **Remedy**: start a session in the slot (`hal2-cli-git worktree run <NN> --agent claude --detach --prompt
  "/handoff c"`), or ask the user when the plan looks abandoned.

## R8 · A system-wide stop paused a landing

- **Signature**: the landing's agent says it was paused by stop-all-agent-work, and the queue was released.
- **Remedy**: after continue-all-agent-work, landings that were aborted start again first.

## R9 · Real failures

These are not flaky:

- the linker's `__eh_frame section too large`;
- merge conflicts;
- a delivery's `hal2-macos install` exit 65;
- a usage error in a new app's test-unit.

The holder fixes these. The boss may fix them directly in main when several landings share the failure (see SKILL.md).

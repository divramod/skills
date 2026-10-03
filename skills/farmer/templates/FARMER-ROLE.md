---
# The farmer skill's settings for this repository: the user's word, and only the user changes it.
# Nothing is implicit. Only the duties listed here run, each on its own cron
# (5-field cron: minute hour day-of-month month day-of-week, local time).
duties:
  mtm: "*/15 * * * *"         # merge-to-main-boss: finished work onto main
  lead: "*/15 * * * *"        # development-lead: unstick sessions
  ci: "*/30 * * * *"          # GitHub Actions green
  watch: "*/15 * * * *"       # sanity-watch: resume abnormal stops
  autoclear: "0 * * * *"      # fix-autoclear: autoclear failures
servant_limit: 5               # farmer-started servants at once (required)
notify: every-round           # every-round | hourly | daily | never (required)
---

# <repo>'s farmer role

The farmer gets <repo> running and keeps it running, autonomously wherever possible.

## Priorities

1. <what must never be down or red>

## Rules

- <what the farmer may decide here, what it must leave to the user>

## Tasks

### <task name>

- **Cron**: `*/15 * * * *`
- **Check**: <what to look at, a command>
- **Act**: <what the farmer does: delegate a fix, notify, or a right this task grants, such as a redeploy>
- **Done when**: <the check that says it is fine>

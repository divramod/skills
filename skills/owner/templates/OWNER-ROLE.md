---
# The owner skill's settings for this repository (the user's word; only the user changes this file).
duties: [mtm, lead, ci, watch, autoclear]   # drop what this repository does not need
rhythm:                                     # each duty's own rhythm: round | 15m | 1h | daily HH:MM
  mtm: 15m
  lead: 15m
  ci: 30m
  watch: 15m
  autoclear: 1h
worker_limit: 5
notify: every-round                         # every-round | hourly | daily | never
---

# <repo>'s owner role

The owner gets <repo> running and keeps it running, autonomously wherever possible.

## Priorities

1. <what must never be down or red>
2. Finished work lands.

## Rules

- <what the owner may decide here, what it must leave to the user>

## Tasks

### <task name>

- **Every**: 15m | 1h | daily 09:07 | round   (its own rhythm; 15m for important ones)
- **Check**: <what to look at, a command>
- **Act**: <what the owner does: delegate a fix, notify, or a right this task grants (e.g. a redeploy)>
- **Done when**: <the check that says it is fine>

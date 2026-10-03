# Woken for the round frame (frame)

| Kind | Do |
|---|---|
| `mfm-failed` | merge-from-main in the owner slot failed (conflict, a setup task, a hook). The owner never changes its branch beyond OWNER-ROLE.md: a conflict outside it means main and the owner branch disagree on a file the owner must not hold. Read the evidence; `git merge --abort` when a merge is half done, notify the user with the files. A failing setup task: delegate its fix |
| `role-invalid`, `role-gone` | Notices: push them to the user. Never edit OWNER-ROLE.md |
| `no-handler` | A due duty without a tick handler: run it as its subskill says |

Log each: `python3 $S/mtm_scan.py record <kind> - "<what>" --note "<why>"`.

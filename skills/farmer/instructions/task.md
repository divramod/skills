# Woken for an OWNER-ROLE.md task (task)

The item names the task. Read its section in the owner slot's `OWNER-ROLE.md` (`## Tasks` › `### <name>`); it is
the user's word and may widen or narrow your authority for that task only. Log every use of a widened right.

- **not in the machine form**: run its Check and Act as written, then log it
  (`python3 $S/mtm_scan.py record task - "<name>: <what>" --note "<why>"`). Offer the user the machine form
  (Check: backticked commands only; Act: commands and `notify|delegate|wake`) in the notification, as a proposal:
  only the user edits OWNER-ROLE.md.
- **its Check still fails after the Act** (`wake` in its Still failing): find out why from the Check's output;
  fix it through a worker (`python3 $S/owner.py delegate --brief <file> --title <title>`) or notify the user.

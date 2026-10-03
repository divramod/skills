import datetime as dt
import unittest

import due

ROLE = """---
duties: [mtm, lead, ci]
rhythm:
  ci: 1h
---

# x

## Tasks

### n8n stays up

- **Every**: 15m
- **Check**: curl

### Disabled tests come back

- **Every**: daily 09:07

### No rhythm given

- **Check**: something

## Notes

### not a task
"""


class Rhythms(unittest.TestCase):
    def test_the_forms_a_rhythm_takes(self):
        self.assertEqual(due.parse_rhythm("round"), ("round", 0))
        self.assertEqual(due.parse_rhythm("15m"), ("every", 15))
        self.assertEqual(due.parse_rhythm("2h"), ("every", 120))
        self.assertEqual(due.parse_rhythm("hourly"), ("every", 60))
        self.assertEqual(due.parse_rhythm("daily 09:07"), ("daily", (9, 7)))
        self.assertEqual(due.parse_rhythm("day, 18:30"), ("daily", (18, 30)))
        with self.assertRaises(ValueError):
            due.parse_rhythm("sometimes")

    def test_due_by_interval_and_by_daily_time(self):
        now = dt.datetime(2026, 10, 3, 10, 0)
        self.assertTrue(due.is_due("15m", None, now))
        self.assertFalse(due.is_due("15m", now - dt.timedelta(minutes=5), now))
        self.assertTrue(due.is_due("15m", now - dt.timedelta(minutes=14), now))  # a tick's jitter counts
        self.assertTrue(due.is_due("daily 09:07", now - dt.timedelta(days=1), now))
        self.assertFalse(due.is_due("daily 09:07", now.replace(hour=9, minute=10), now))
        self.assertFalse(due.is_due("daily 11:00", None, now))
        self.assertTrue(due.is_due("round", now, now))


class Schedule(unittest.TestCase):
    def test_duties_from_front_matter_and_tasks_with_their_rhythm(self):
        s = due.schedule(ROLE)
        self.assertEqual(s, {"duty:mtm": "15m", "duty:lead": "15m", "duty:ci": "1h",
                             "task:n8n stays up": "15m", "task:Disabled tests come back": "daily 09:07",
                             "task:No rhythm given": "hourly"})
        self.assertEqual(due.tick(s), 15)

    def test_no_role_file_runs_every_duty_with_its_default(self):
        s = due.schedule("")
        self.assertEqual(set(s), {f"duty:{d}" for d in due.DUTIES})
        self.assertEqual(due.tick({"a": "2m"}), 5)


if __name__ == "__main__":
    unittest.main()

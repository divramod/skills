"""plan.py: create, list, switch and update single-file plans."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "plan.py"

EXISTING = """# Plan 0002: migrate daily tools

| # | Step | Status |
|---|---|---|
| 1 | git status | done (`c649bd5`) |
| 2 | move nvim | next |
| 3 | shooter | |
"""


class PlanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.root, check=True)
        self.plans = self.root / "plans"

    def tearDown(self):
        self.tmp.cleanup()

    def run_plan(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), *args],
                              capture_output=True, text=True)

    def plan(self, *args) -> dict:
        result = self.run_plan(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_new_numbers_after_existing_and_becomes_current(self):
        self.plans.mkdir(parents=True)
        (self.plans / "0002-migrate-daily-tools.md").write_text(EXISTING)
        (self.plans / "0001-old").mkdir()  # old-format plan folder is ignored

        info = self.plan("new", "Lean Shooter CLI!", "--goal", "Replace the old binary.")

        self.assertEqual(info["slug"], "0003-lean-shooter-cli")
        self.assertTrue(info["current"])
        self.assertEqual((self.plans / "CURRENT_PLAN").read_text(), "0003-lean-shooter-cli\n")
        text = (self.plans / "0003-lean-shooter-cli.md").read_text()
        self.assertIn("# Plan 0003: Lean Shooter CLI!", text)
        self.assertIn("Replace the old binary.", text)
        self.assertEqual(info["total"], 1)

    def test_current_reports_progress_and_next_step(self):
        self.plans.mkdir(parents=True)
        (self.plans / "0002-migrate-daily-tools.md").write_text(EXISTING)
        (self.plans / "CURRENT_PLAN").write_text("0002-migrate-daily-tools\n")

        info = self.plan("current")

        self.assertEqual((info["done"], info["total"]), (1, 3))
        self.assertEqual(info["next"]["number"], "2")
        self.assertEqual(info["next"]["done_when"], "")
        self.assertEqual(info["grilled"], "")

    def test_status_updates_one_cell(self):
        self.plans.mkdir(parents=True)
        (self.plans / "0002-migrate-daily-tools.md").write_text(EXISTING)
        (self.plans / "CURRENT_PLAN").write_text("0002-migrate-daily-tools\n")

        self.plan("status", "2", "done (`916a934`)")
        info = self.plan("status", "3", "next")

        self.assertEqual(info["done"], 2)
        self.assertEqual(info["next"]["step"], "shooter")
        self.assertIn("| 2 | move nvim | done (`916a934`) |", (self.plans / "0002-migrate-daily-tools.md").read_text())

    def test_use_accepts_number_and_grilled_stamps_date(self):
        self.plans.mkdir(parents=True)
        (self.plans / "0002-migrate-daily-tools.md").write_text(EXISTING)

        self.plan("use", "2")
        info = self.plan("grilled")

        self.assertTrue(info["current"])
        self.assertRegex(info["grilled"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual(self.plan("grilled")["grilled"], info["grilled"])  # idempotent, one line

    def test_errors(self):
        self.assertEqual(self.run_plan("current").returncode, 1)
        self.plans.mkdir(parents=True)
        (self.plans / "0002-migrate-daily-tools.md").write_text(EXISTING)
        self.assertEqual(self.run_plan("use", "9").returncode, 1)
        self.assertEqual(self.run_plan("status", "7", "x", "--plan", "2").returncode, 1)
        self.assertEqual(self.run_plan("new", "!!!").returncode, 1)


if __name__ == "__main__":
    unittest.main()

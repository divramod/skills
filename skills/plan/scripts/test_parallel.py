"""plan.py on a parallel plan (skills plan 0013): Needs, Touches, Who, ready, assign, brief, report, reports, watch."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "plan.py"
SLUG = "0005-big-plan"

PARALLEL = r"""# Plan 0005: big plan

Landing: auto

## Steps

| # | Step | Needs | Touches | Who | Done when | Status |
|---|---|---|---|---|---|---|
| 1 | proto | | proto:core | lead | protos build | done |
| 2 | server a \| b | 1 | rust:server | slot 31 | cargo test | running |
| 3 | client | 1 | ts:client | | npm test | |
| 4 | more server | 1 | rust:server | | cargo test | |
| 5 | vm one | 1 | @vm | | vm up | |
| 6 | vm two | 1 | @vm | | vm up | |
| 7 | vm three | 1 | @vm | | vm up | |
| 8 | Milestone 1: land the server | 2-4 | | lead | main green | |
| 9 | Write the UATs | 1-8 | docs | lead | after the landing: the UATs pass | |
"""

SEQUENTIAL = """# Plan 0001: old plan

| # | Step | Status |
|---|---|---|
| 1 | one | next |
"""


def git(cwd: Path, *args: str) -> str:
    out = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd,
                         capture_output=True, text=True, check=True)
    return out.stdout


class ParallelTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base / "02"  # the lead's slot
        self.root.mkdir()
        git(self.root, "init", "-q", "-b", "main")
        self.plans = self.root / "plans"
        self.path = self.write_plan(SLUG, PARALLEL)
        (self.plans / "CURRENT_PLAN").write_text(SLUG + "\n")

    def tearDown(self):
        self.tmp.cleanup()

    def write_plan(self, slug: str, text: str) -> Path:
        path = self.plans / slug / "plan.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def run_plan(self, *args, root=None) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT), "--root", str(root or self.root), *args],
                              capture_output=True, text=True)

    def plan(self, *args, root=None) -> dict:
        result = self.run_plan(*args, root=root)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def refused(self, *args, root=None) -> str:
        result = self.run_plan(*args, root=root)
        self.assertEqual(result.returncode, 1, result.stdout)
        return result.stderr

    def ready(self, *args) -> dict:
        return self.plan("ready", "--json", *args)

    def numbers(self, steps: list[dict]) -> list[str]:
        return [s["number"] for s in steps]

    def row(self, step: str) -> str:
        return next(l for l in self.path.read_text().splitlines() if l.startswith(f"| {step} |"))

    # the table

    def test_escaped_pipe_is_read_and_written_back(self):
        info = self.plan("current")
        self.assertEqual(info["steps"][1]["step"], "server a | b")
        self.assertTrue(info["parallel"])

        self.plan("status", "2", "done (`abc1234`)")

        self.assertEqual(self.row("2"), r"| 2 | server a \| b | 1 | rust:server | slot 31 | cargo test | done (`abc1234`) |")

    def test_short_row_is_a_clean_error_and_list_keeps_other_plans(self):
        self.write_plan("0006-broken", PARALLEL.replace("| 3 | client | 1 | ts:client | | npm test | |", "| 3 | a | b |"))
        (self.plans / "CURRENT_PLAN").write_text("0006-broken\n")

        error = self.refused("current")
        self.assertIn("row 3 of the step table has 3 cells, its header 7", error)
        self.assertNotIn("Traceback", error)
        plans = {p["slug"]: p for p in self.plan("list")}
        self.assertEqual(plans[SLUG]["total"], 9)
        self.assertIn("row 3", plans["0006-broken"]["problems"][0])

    def test_new_parallel_has_the_columns_and_the_uat_row_needs_every_step(self):
        info = self.plan("new", "more work", "--parallel")

        text = (self.root / info["path"]).read_text()
        self.assertIn("| # | Step | Needs | Touches | Who | Done when | Status |", text)
        self.assertTrue(info["parallel"])
        uat = info["steps"][-1]
        self.assertEqual((uat["needs"], uat["touches"], uat["who"]), (["1"], ["docs"], "lead"))
        self.assertEqual(info["steps"][0]["needs"], [])
        self.assertEqual(info["problems"], [])

    def test_sequential_plan_has_no_parallel_keys_and_refuses_ready(self):
        self.write_plan("0001-old-plan", SEQUENTIAL)

        info = self.plan("use", "1")
        self.assertNotIn("parallel", info)
        self.assertNotIn("needs", info["steps"][0])
        self.assertIn("is no parallel plan", self.refused("ready"))

    # ready

    def test_ready_honours_needs_touches_and_vm_room(self):
        info = self.ready()

        self.assertEqual(self.numbers(info["ready"]), ["3", "5", "6"])
        self.assertEqual(self.numbers(info["running"]), ["2"])
        why = {w["number"]: w["why"] for w in info["waiting"]}
        self.assertEqual(why["4"], "touches rust:server, in use")
        self.assertEqual(why["7"], "touches @vm, in use")
        self.assertEqual(why["8"], "needs step(s) 2, 3, 4")
        self.assertEqual(why["9"], "checked after the landing")
        self.assertEqual(self.numbers(self.plan("current")["ready"]), ["3", "5", "6"])

    def test_ready_limit_and_plain_output(self):
        self.assertEqual(self.numbers(self.ready("--limit", "1")["ready"]), ["3"])
        self.assertEqual(self.ready("--limit", "1")["waiting"][1]["why"], "the limit of 1 is reached")

        out = self.run_plan("ready").stdout.splitlines()
        self.assertEqual(out[0], "3\tclient\tts:client")
        self.assertEqual(len(out), 3)

    def test_capacity_line_overrides_the_room(self):
        self.path.write_text(PARALLEL.replace("Landing: auto\n", "Landing: auto\n\nCapacity: @vm=3, rust:server=2\n"))

        self.assertEqual(self.numbers(self.ready()["ready"]), ["3", "4", "5", "6", "7"])

    def test_milestones_touch_land_so_only_one_runs(self):
        self.path.write_text(PARALLEL.replace("| 2-4 |", "| 1 |").replace(
            "| 9 | Write the UATs", "| 10 | milestone 2: land the client | 1 | | lead | main green | |\n| 9 | Write the UATs"))

        info = self.ready()
        self.assertIn("@land", info["ready"][-1]["touches"])
        self.assertEqual(self.numbers(info["ready"])[-1], "8")
        self.assertEqual({w["number"]: w["why"] for w in info["waiting"]}["10"], "touches @land, in use")

    def test_done_needs_free_the_waiting_steps(self):
        for step in ("2", "3"):
            self.plan("status", step, "done")

        self.assertEqual(self.numbers(self.ready()["ready"]), ["4", "5", "6"])

    # problems

    def test_problems_name_bad_ids_needs_and_cycles(self):
        self.path.write_text(PARALLEL.replace("| 3 | client | 1 |", "| 3 | client | 4, x |")
                             .replace("| 4 | more server | 1 |", "| 4 | more server | 3, 12 |")
                             .replace("| 6 | vm two |", "| 5 | vm two |")
                             .replace("| 7 | vm three |", "| 7a | vm three |"))

        problems = self.plan("current")["problems"]

        self.assertIn("step 3: Needs 'x' are no step ids or ranges", problems)
        self.assertIn("step 4 needs step(s) 12, which no row has", problems)
        self.assertIn("step id '5' is used twice", problems)
        self.assertTrue(any("'7a' is no integer" in p for p in problems), problems)
        self.assertIn("the Needs form a cycle: 3 -> 4 -> 3", problems)

    # assign

    def test_assign_refuses_a_step_that_is_not_ready_unless_forced(self):
        self.assertIn("step 4 is not ready (touches rust:server, in use)", self.refused("assign", "4", "subagent"))
        self.assertIn("step 2 is not ready (it is running)", self.refused("assign", "2", "lead"))

        info = self.plan("assign", "4", "subagent", "--force")

        self.assertEqual((info["steps"][3]["who"], info["steps"][3]["status"]), ("subagent", "running"))

    def test_assign_checks_who_and_slots_30_up(self):
        self.assertIn("subservants work only in slots 30-99", self.refused("assign", "3", "slot", "12"))
        self.assertIn("none of lead, subagent, user, slot NN", self.refused("assign", "3", "bob"))

        info = self.plan("assign", "3", "Slot", "33")

        self.assertEqual(self.row("3"), "| 3 | client | 1 | ts:client | slot 33 | npm test | running |")
        self.assertNotIn("marker", info)  # no worktree 33 exists
        self.assertEqual(self.numbers(info["running"]), ["2", "3"])

    def test_assign_to_an_existing_slot_writes_its_marker(self):
        git(self.root, "commit", "-q", "--allow-empty", "-m", "init")
        git(self.root, "worktree", "add", "-q", "-b", "31", str(self.base / "31"))

        info = self.plan("assign", "3", "slot", "31")

        slot = self.base / "31"
        self.assertEqual(Path(info["marker"]).resolve(), (slot / "plans" / "LEAD").resolve())
        self.assertEqual((slot / "plans" / "LEAD").read_text(), f"02 {SLUG} 3\n")
        self.assertEqual((slot / "plans" / "CURRENT_PLAN").read_text(), SLUG + "\n")

    # the subservant's slot

    def test_a_marked_slot_refuses_writes_to_the_plan(self):
        before = self.path.read_text()
        (self.plans / "LEAD").write_text(f"02 {SLUG} 3\n")

        for args in (("new", "x"), ("status", "3", "done"), ("assign", "3", "lead"), ("grilled",),
                     ("landing", "manual"), ("uat",), ("brief", "3")):
            self.assertIn("is a subservant of slot 02", self.refused(*args), args)
        self.assertEqual(self.path.read_text(), before)
        self.assertEqual(self.plan("current")["lead"], {"slot": "02", "plan": SLUG, "step": "3"})
        report = self.plan("report", "3")
        self.assertEqual(report["report"], f"plans/{SLUG}/reports/3.md")
        text = (self.root / report["report"]).read_text()
        self.assertIn(f"# Report: step 3 of plan {SLUG}", text)
        self.assertIn("Slot 02 for the lead in slot 02", text)
        self.assertEqual(self.numbers(self.ready()["ready"]), ["3", "5", "6"])

    def test_a_broken_marker_is_a_clean_error(self):
        (self.plans / "LEAD").write_text("02\n")

        self.assertIn("must hold `<lead-slot> <plan> <step>`", self.refused("current"))

    # brief and report

    def test_brief_scaffolds_once_and_prints_the_prompt(self):
        info = self.plan("brief", "3")

        brief = self.root / info["brief"]
        self.assertEqual(info["brief"], f"plans/{SLUG}/steps/3.md")
        text = brief.read_text()
        self.assertIn(f"# Step 3 of plan {SLUG}: client", text)
        self.assertIn("- Needs: 1 (done; their work is on origin/02)", text)
        self.assertIn("- Touches: ts:client", text)
        self.assertIn("npm test", text)
        self.assertIn("subservant of plan 0005-big-plan, step 3 only, for the lead in slot 02", info["prompt"])
        self.assertIn(f"plans/{SLUG}/steps/3.md", info["prompt"])
        self.assertIn("never land", info["prompt"])

        brief.write_text("edited by the lead")
        self.plan("brief", "3")
        self.assertEqual(brief.read_text(), "edited by the lead")

    def test_brief_and_report_refuse_an_unknown_step(self):
        self.assertIn("no step '42'", self.refused("brief", "42"))
        self.assertIn("no step '42'", self.refused("report", "42"))

    # reports and watch

    def test_reports_and_watch_find_a_report_pushed_to_the_slot_branch(self):
        origin = self.base / "origin.git"
        git(self.base, "init", "-q", "--bare", str(origin))
        git(self.root, "commit", "-q", "--allow-empty", "-m", "init")
        git(self.root, "remote", "add", "origin", str(origin))
        git(self.root, "worktree", "add", "-q", "-b", "31", str(self.base / "31"))
        self.assertEqual(self.plan("reports")["arrived"], [])

        slot = self.base / "31"
        report = slot / "plans" / SLUG / "reports" / "2.md"
        report.parent.mkdir(parents=True)
        report.write_text("# Report\n")
        git(slot, "add", "plans")
        git(slot, "commit", "-q", "-m", "report (plan 0005 step 2)")
        git(slot, "push", "-q", "origin", "31")

        arrived = self.plan("reports")["arrived"]
        sha = git(slot, "rev-parse", "--short", "HEAD").strip()
        self.assertEqual(arrived, [{"number": "2", "step": "server a | b", "slot": "31", "sha": sha,
                                    "report": f"plans/{SLUG}/reports/2.md"}])
        watch = self.run_plan("watch", "--interval", "0", "--rounds", "2")
        self.assertEqual(watch.returncode, 0, watch.stderr)
        self.assertEqual(watch.stdout, f"report step 2 from slot 31 at {sha}: plans/{SLUG}/reports/2.md\n")

    def test_reports_skip_steps_that_are_not_running_subservants(self):
        self.plan("status", "2", "done")

        self.assertEqual(self.plan("reports", "--no-fetch")["arrived"], [])


if __name__ == "__main__":
    unittest.main()

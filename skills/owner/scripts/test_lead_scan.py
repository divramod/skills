import json
import tempfile
import time
import unittest
from pathlib import Path

import lead_scan as lead


def agent(**over):
    base = {"state": "done", "since": int((time.time() - 3600) * 1000), "plan": "", "context_percent": 20}
    base.update(over)
    return base


class Classify(unittest.TestCase):
    def test_a_question_to_the_user_needs_help(self):
        self.assertEqual(lead.classify(agent(), "Which option do you want?", time.time())[0], "asks")
        self.assertEqual(lead.classify(agent(), "AskUserQuestion: Land now?", time.time())[0], "asks")
        self.assertEqual(lead.classify(agent(), "Waiting for the user to unlock the Mac.", time.time())[0], "asks")

    def test_a_finished_report_outside_a_plan_needs_none(self):
        self.assertIsNone(lead.classify(agent(), "Done. All tests pass.", time.time()))

    def test_idle_inside_a_plan_and_blocked_dialogs(self):
        self.assertEqual(lead.classify(agent(plan="0094 n8n"), "Step 6 done.", time.time())[0], "idle-in-plan")
        fresh = agent(state="blocked", since=int(time.time() * 1000))
        self.assertIsNone(lead.classify(fresh, "", time.time()))
        self.assertEqual(lead.classify(agent(state="blocked"), "", time.time())[0], "blocked")

    def test_a_working_session_needs_help_only_near_its_context_limit(self):
        self.assertIsNone(lead.classify(agent(state="working"), "Should I?", time.time()))
        self.assertEqual(lead.classify(agent(state="working", context_percent=91), "", time.time())[0],
                         "context-high")


    def test_a_working_slot_without_current_plan_is_told_to_fill_it(self):
        self.assertEqual(lead.classify(agent(state="working", slot="07"), "", time.time())[0], "no-plan")
        self.assertIsNone(lead.classify(agent(state="working", slot="07", current_plan="0094-n8n"), "", time.time()))
        self.assertIsNone(lead.classify(agent(state="working", slot="main"), "", time.time()))


class Transcript(unittest.TestCase):
    def test_the_last_assistant_text_or_question_is_read(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.jsonl"
            rows = [
                {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "old"}]}},
                {"type": "user", "message": {"role": "user", "content": "go"}},
                {"type": "assistant", "message": {"role": "assistant", "content": [
                    {"type": "tool_use", "name": "AskUserQuestion",
                     "input": {"questions": [{"question": "Land now?"}]}}]}},
            ]
            p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
            self.assertEqual(lead.last_assistant_text(p), "AskUserQuestion: Land now?")
            self.assertEqual(lead.last_assistant_text(Path(d) / "missing.jsonl"), "")

    def test_the_transcript_path_munges_the_cwd(self):
        self.assertTrue(str(lead.transcript("/Users/mod/.hal/git/worktree/hal2/04", "x")).endswith(
            "-Users-mod--hal-git-worktree-hal2-04/x.jsonl"))


if __name__ == "__main__":
    unittest.main()

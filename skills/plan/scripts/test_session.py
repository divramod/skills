"""session.py: the session's model and effort against the next step's."""
import json
import tempfile
import unittest
from pathlib import Path

import session


def tree(*procs):
    """A fake process table: pid → (parent, command line), the first entry's pid is 100, each the next's child."""
    table = {100 + i: (101 + i, args) for i, args in enumerate(procs)}
    return lambda pid: table.get(pid)


class SessionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = Path(self.tmp.name) / "settings.json"
        self.settings.write_text(json.dumps({"model": "opus",
                                             "modelSettings": {"claude-opus-5-5": {"effortLevel": "medium"}}}))

    def tearDown(self):
        self.tmp.cleanup()

    def test_flags_of_the_nearest_claude(self):
        lookup = tree("python3 plan.py current", "/bin/zsh",
                      "claude --remote-control hal2-03 --model opus[1m] --effort high -- /handoff c", "tmux")
        self.assertEqual(session.current(100, self.settings, lookup), {"model": "opus[1m]", "effort": "high"})

    def test_settings_without_flags(self):
        lookup = tree("/bin/zsh", "claude --continue", "sh")
        self.assertEqual(session.current(100, self.settings, lookup), {"model": "opus", "effort": "medium"})

    def test_no_claude_above_is_unknown(self):
        self.assertIsNone(session.current(100, self.settings, tree("/bin/zsh", "codex")))

    def test_prompt_after_double_dash_is_no_flag(self):
        self.assertEqual(session.flag(["--", "--model", "haiku"], "--model"), "")

    def test_switch_when_model_family_differs(self):
        switch = session.switch_for({"model": "sonnet", "effort": "medium"}, {"model": "opus[1m]", "effort": "medium"})
        self.assertEqual((switch["model"], switch["effort"]), ("sonnet", "medium"))

    def test_switch_when_effort_differs(self):
        self.assertIsNotNone(session.switch_for({"model": "opus", "effort": "high"},
                                                {"model": "claude-opus-5-5", "effort": "medium"}))

    def test_no_switch_for_the_same_family_and_effort(self):
        self.assertIsNone(session.switch_for({"model": "opus", "effort": "high"},
                                             {"model": "opus[1m]", "effort": "high"}))

    def test_no_switch_without_values_or_session(self):
        self.assertIsNone(session.switch_for({"model": "", "effort": ""}, {"model": "opus", "effort": "low"}))
        self.assertIsNone(session.switch_for({"model": "sonnet", "effort": "low"}, None))


if __name__ == "__main__":
    unittest.main()

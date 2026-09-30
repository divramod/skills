import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import evidence  # noqa: E402


class TranscriptTail(unittest.TestCase):
    def test_tools_denials_and_prompts(self):
        rows = [
            {"timestamp": "2026-09-30T10:14:35.922Z", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": "git commit -m x"}}]}},
            {"timestamp": "2026-09-30T10:14:35.990Z", "message": {"role": "user", "content": [
                {"type": "tool_result", "content": "PreToolUse:Bash hook error: hal2: context at 36.2%"}]}},
            {"timestamp": "2026-09-30T10:14:35.990Z", "attachment": {
                "type": "hook_stopped_continuation", "message": "stopped for the hand-off"}},
            {"timestamp": "2026-09-30T10:14:37.245Z", "message": {"role": "user", "content": "hal2 stopped this turn"}},
            {"timestamp": "2026-09-30T10:14:38.000Z", "message": {"role": "user", "content": [
                {"type": "tool_result", "content": "plain output"}]}},
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            f.write("\n".join(json.dumps(r) for r in rows) + "\nnot json\n")
        lines = evidence.transcript_tail(Path(f.name))
        self.assertEqual(len(lines), 4)
        self.assertIn("TOOL Bash", lines[0])
        self.assertIn("hook error", lines[1])
        self.assertIn("HOOK-STOP", lines[2])
        self.assertIn("hal2 stopped this turn", lines[3])


class Selfcheck(unittest.TestCase):
    def test_drift_is_reported(self):
        with tempfile.TemporaryDirectory() as repo:
            src = Path(repo) / evidence.SRC
            src.mkdir(parents=True)
            (src / "autoclear.rs").write_text('"waiting" REARM_POINTS MAX_ATTEMPTS DEFAULT_PROMPT')
            skill = Path(repo) / "SKILL.md"
            skill.write_text(
                "`code/rust/libs/hal2-agents/src/autoclear.rs` `code/rust/libs/hal2-agents/src/gone.rs`\n"
                "<!-- names -->`waiting` `vanished-state`<!-- /names -->\n`REARM_POINTS` `HANDOFF_SCRIPTS`\n"
            )
            evidence.SKILL_MD = skill
            args = type("A", (), {"repo": repo})()
            out = []
            real_print = print
            try:
                evidence.print = lambda *a, **k: out.append(" ".join(map(str, a)))
                code = evidence.selfcheck(args)
            finally:
                evidence.print = real_print
            text = "\n".join(out)
            self.assertEqual(code, 1)
            self.assertIn("gone.rs", text)
            self.assertIn("vanished-state", text)
            self.assertIn("HANDOFF_SCRIPTS", text)
            self.assertNotIn("DRIFT name `waiting`", text)


if __name__ == "__main__":
    unittest.main()

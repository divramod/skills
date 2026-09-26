"""context.py: context-window fill from a Claude Code transcript."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "context.py"


def assistant(input_tokens, cache_read=0, cache_write=0, output=0, sidechain=False) -> str:
    return json.dumps({"type": "assistant", "isSidechain": sidechain, "message": {"usage": {
        "input_tokens": input_tokens, "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": cache_write, "output_tokens": output}}})


class ContextTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.projects = self.home / ".claude" / "projects" / "-some-repo"
        self.projects.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def transcript(self, *lines, session="s1") -> Path:
        path = self.projects / f"{session}.jsonl"
        path.write_text("\n".join(lines) + "\n")
        return path

    def run_context(self, *args, env=None) -> dict:
        full_env = {"HOME": str(self.home), "PATH": os.environ.get("PATH", "")}
        full_env.update(env or {})
        out = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                             env=full_env, check=True)
        return json.loads(out.stdout)

    def test_uses_the_last_main_chain_call(self):
        self.transcript(
            assistant(10, cache_read=1000),
            json.dumps({"type": "user", "message": {"content": "hi"}}),
            "not json",
            assistant(20, cache_read=60_000, cache_write=19_000, output=980),
            assistant(5, cache_read=190_000, sidechain=True),
        )
        result = self.run_context(env={"CLAUDE_CODE_SESSION_ID": "s1"})
        self.assertEqual(result["used"], 80_000)
        self.assertEqual(result["window"], 200_000)
        self.assertEqual(result["percent"], 40.0)
        self.assertTrue(result["stop"])

    def test_threshold_and_window_arguments(self):
        path = self.transcript(assistant(0, cache_read=100_000))
        result = self.run_context("--transcript", str(path), "--window", "1000000", "--threshold", "40")
        self.assertEqual(result["percent"], 10.0)
        self.assertFalse(result["stop"])

    def test_window_from_a_1m_model_setting_or_the_environment(self):
        self.transcript(assistant(0, cache_read=100_000))
        (self.home / ".claude" / "settings.json").write_text(json.dumps({"model": "opus[1m]"}))
        self.assertEqual(self.run_context(env={"CLAUDE_CODE_SESSION_ID": "s1"})["window"], 1_000_000)
        env = {"CLAUDE_CODE_SESSION_ID": "s1", "CLAUDE_CONTEXT_WINDOW": "500000"}
        self.assertEqual(self.run_context(env=env)["percent"], 20.0)

    def test_more_used_than_the_default_window_means_the_large_one(self):
        self.transcript(assistant(0, cache_read=300_000))
        result = self.run_context(env={"CLAUDE_CODE_SESSION_ID": "s1"})
        self.assertEqual(result["window"], 1_000_000)
        self.assertEqual(result["percent"], 30.0)

    def test_unknown_without_session_or_usage(self):
        result = self.run_context()
        self.assertFalse(result["known"])
        self.assertIsNone(result["stop"])
        self.transcript(json.dumps({"type": "user"}))
        result = self.run_context(env={"CLAUDE_CODE_SESSION_ID": "s1"})
        self.assertFalse(result["known"])
        self.assertIn("no usage", result["source"])
        self.assertFalse(self.run_context(env={"CLAUDE_CODE_SESSION_ID": "other"})["known"])


if __name__ == "__main__":
    unittest.main()

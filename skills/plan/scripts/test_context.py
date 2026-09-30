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
        full_env = {"HOME": str(self.home), "PATH": os.environ.get("PATH", ""),
                    "HAL2_CLI_AGENTS": str(self.home / "no-hal2-cli-agents")}
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
        # 80k of the usable 167k (200k minus the auto-compact buffer).
        self.assertEqual(result["raw_percent"], 40.0)
        self.assertEqual(result["percent"], 47.9)
        self.assertTrue(result["stop"])

    def test_threshold_and_window_arguments(self):
        path = self.transcript(assistant(0, cache_read=100_000))
        result = self.run_context("--transcript", str(path), "--window", "1000000", "--threshold", "40")
        self.assertEqual(result["percent"], 12.0)
        self.assertFalse(result["stop"])

    def test_window_from_a_1m_model_setting_or_the_environment(self):
        self.transcript(assistant(0, cache_read=100_000))
        (self.home / ".claude" / "settings.json").write_text(json.dumps({"model": "opus[1m]"}))
        self.assertEqual(self.run_context(env={"CLAUDE_CODE_SESSION_ID": "s1"})["window"], 1_000_000)
        env = {"CLAUDE_CODE_SESSION_ID": "s1", "CLAUDE_CONTEXT_WINDOW": "500000"}
        self.assertEqual(self.run_context(env=env)["raw_percent"], 20.0)

    def test_more_used_than_the_default_window_means_the_large_one(self):
        self.transcript(assistant(0, cache_read=300_000))
        result = self.run_context(env={"CLAUDE_CODE_SESSION_ID": "s1"})
        self.assertEqual(result["window"], 1_000_000)
        self.assertEqual(result["raw_percent"], 30.0)
        self.assertEqual(result["percent"], 35.9)

    def test_matches_the_statusline_formula(self):
        # The statusline showed 46% at 381,685 tokens of a 1M window.
        path = self.transcript(assistant(0, cache_read=381_685))
        result = self.run_context("--transcript", str(path), "--window", "1000000")
        self.assertEqual(round(result["percent"]), 46)
        self.assertTrue(result["stop"])

    def test_unknown_without_session_or_usage(self):
        result = self.run_context()
        self.assertFalse(result["known"])
        self.assertIsNone(result["stop"])
        self.transcript(json.dumps({"type": "user"}))
        result = self.run_context(env={"CLAUDE_CODE_SESSION_ID": "s1"})
        self.assertFalse(result["known"])
        self.assertIn("no usage", result["source"])
        self.assertFalse(self.run_context(env={"CLAUDE_CODE_SESSION_ID": "other"})["known"])


    def fake_agents(self, settings_json: str) -> str:
        program = self.home / "hal2-cli-agents"
        program.write_text(f"#!/bin/sh\n[ \"$1 $2\" = \"settings --json\" ] && echo '{settings_json}'\n")
        program.chmod(0o755)
        return str(program)

    def test_default_threshold_is_35_without_hal2(self):
        path = self.transcript(assistant(100_000))
        result = self.run_context("--transcript", str(path))
        self.assertEqual(result["threshold"], 35.0)
        self.assertFalse(result["autoclear"])
        self.assertIn("settings", result["autoclear_reason"])

    def test_threshold_and_autoclear_from_hal2_settings(self):
        path = self.transcript(assistant(100_000))
        program = self.fake_agents('{"autoclear": {"enabled": true, "percent": 10}}')
        env = {"HAL2_CLI_AGENTS": program, "CLAUDE_CODE_SESSION_ID": "s1", "TMUX_PANE": "%3"}
        result = self.run_context("--transcript", str(path), env=env)
        self.assertEqual(result["threshold"], 10.0)
        self.assertTrue(result["stop"])
        self.assertTrue(result["autoclear"])
        self.assertEqual(result["autoclear_reason"], "")
        # --threshold still wins.
        self.assertEqual(self.run_context("--transcript", str(path), "--threshold", "50", env=env)["threshold"], 50.0)

    def test_no_autoclear_when_disabled_or_outside_tmux(self):
        path = self.transcript(assistant(100_000))
        disabled = self.fake_agents('{"autoclear": {"enabled": false, "percent": 35}}')
        result = self.run_context("--transcript", str(path), env={
            "HAL2_CLI_AGENTS": disabled, "CLAUDE_CODE_SESSION_ID": "s1", "TMUX_PANE": "%3"})
        self.assertFalse(result["autoclear"])
        self.assertIn("disabled", result["autoclear_reason"])
        enabled = self.fake_agents('{"autoclear": {"enabled": true, "percent": 35}}')
        result = self.run_context("--transcript", str(path), env={
            "HAL2_CLI_AGENTS": enabled, "CLAUDE_CODE_SESSION_ID": "s1"})
        self.assertFalse(result["autoclear"])
        self.assertIn("TMUX_PANE", result["autoclear_reason"])
        self.assertIn("HAL2_TERMINAL", result["autoclear_reason"])

    def test_autoclear_in_a_hal2_terminal_host(self):
        path = self.transcript(assistant(100_000))
        enabled = self.fake_agents('{"autoclear": {"enabled": true, "percent": 35}}')
        result = self.run_context("--transcript", str(path), env={
            "HAL2_CLI_AGENTS": enabled, "CLAUDE_CODE_SESSION_ID": "s1", "HAL2_TERMINAL": "tabc1"})
        self.assertTrue(result["autoclear"])
        self.assertEqual(result["autoclear_reason"], "")


if __name__ == "__main__":
    unittest.main()

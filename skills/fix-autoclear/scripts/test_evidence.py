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


class Labels(unittest.TestCase):
    AGENTS = [
        {"pane_id": "%1", "kind": "claude", "project": "/a/hal2", "slot": "02"},
        {"pane_id": "%2", "kind": "codex", "project": "/a/hal2", "slot": "03"},
        {"pane_id": "%3", "kind": "claude", "project": "/a/other", "slot": "02"},
        {"pane_id": "%4", "kind": "claude", "project": "/a/hal2", "slot": "main"},
    ]

    def test_agents_are_named_by_repo_and_worktree(self):
        self.assertEqual(evidence.label("/a/hal2", "02"), "hal2 wt 02")
        self.assertEqual(evidence.label("/a/hal2", "main"), "hal2 main")
        self.assertEqual(evidence.agent_label(self.AGENTS[0]), "hal2 wt 02")
        self.assertEqual(evidence.agent_label({"pane_id": "%9"}), "the agent in pane %9")

    def test_a_worktree_finds_its_claude_agent(self):
        agent, many = evidence.find_agent(self.AGENTS, "02", "hal2")
        self.assertEqual((agent["pane_id"], many), ("%1", []))
        agent, many = evidence.find_agent(self.AGENTS, "02")
        self.assertIsNone(agent)
        self.assertEqual(many, ["hal2 wt 02", "other wt 02"])
        self.assertEqual(evidence.find_agent(self.AGENTS, "03", "hal2"), (None, []))
        self.assertEqual(evidence.find_agent(self.AGENTS, "main", "hal2")[0]["pane_id"], "%4")

    def test_show_resolves_a_worktree_of_this_repo_first(self):
        real_agents, real_repo = evidence.agents, evidence.current_repo
        try:
            evidence.agents = lambda: self.AGENTS
            evidence.current_repo = lambda: "hal2"
            args = type("A", (), {"pane": None, "session": None, "worktree": "02", "repo": None})()
            pane, agent, problem = evidence.resolve_pane(args)
            self.assertEqual((pane, problem), ("%1", None))
            evidence.current_repo = lambda: None
            pane, agent, problem = evidence.resolve_pane(args)
            self.assertIsNone(pane)
            self.assertIn("hal2 wt 02, other wt 02", problem)
        finally:
            evidence.agents, evidence.current_repo = real_agents, real_repo


class Capture(unittest.TestCase):
    def test_an_incident_becomes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            jobs = tmp / "state/agents/autoclear"
            jobs.mkdir(parents=True)
            (jobs / "54.json").write_text(json.dumps(
                {"state": "failed", "reason": "clear-unconfirmed", "pane": "%54", "old_session": "s1"}))
            (jobs / "54.log").write_text("2026-09-30 10:00:00 clearing\n")
            (jobs / "s1.guard").write_text(json.dumps({"session_id": "s1", "pane": "%54", "stage": "soft"}))
            (jobs / "sweep.log").write_text("2026-09-30 10:00:01   %54 02 s1 context 40% state done plan x: skip\n"
                                            "2026-09-30 10:00:01   %9 03 s9 context 1% state done plan x: skip\n")
            agent = {"pane_id": "%54", "kind": "claude", "project": "/a/hal2", "slot": "02", "session_id": "s1"}
            saved = (evidence.JOBS, evidence.agents, evidence.screen, evidence.current_repo, evidence.need)
            try:
                evidence.JOBS = jobs
                evidence.agents = lambda: [agent]
                evidence.screen = lambda pane: "❯ /clear\n  ─── History 96/100 ───"
                evidence.current_repo = lambda: "hal2"
                evidence.need = lambda tool: None
                args = type("A", (), {"pane": None, "session": None, "worktree": "02", "repo": None,
                                      "out": str(tmp / "out"), "hours": 1e6})()
                self.assertEqual(evidence.capture(args), 0)
            finally:
                evidence.JOBS, evidence.agents, evidence.screen, evidence.current_repo, evidence.need = saved
            out = tmp / "out"
            self.assertIn("History 96/100", (out / "screen.txt").read_text())
            self.assertEqual(json.loads((out / "job.json").read_text())["reason"], "clear-unconfirmed")
            self.assertTrue((out / "job.log").exists() and (out / "marker-s1.json").exists())
            sweep = (out / "sweep.log").read_text()
            self.assertIn("%54", sweep)
            self.assertNotIn("%9 ", sweep)
            readme = (out / "README.md").read_text()
            self.assertIn("hal2 wt 02", readme)
            self.assertIn("src/fixtures/screens", readme)

"""commit-handoff.sh commits the handoff file alone and leaves other changes untouched."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "commit-handoff.sh"
ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
}


def run(repo, *args, check=True):
    return subprocess.run(args, cwd=repo, env=ENV, text=True, capture_output=True, check=check)


class CommitHandoffTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        run(self.repo, "git", "init", "-q", "-b", "main")
        (self.repo / "code.txt").write_text("v1\n")
        run(self.repo, "git", "add", ".")
        run(self.repo, "git", "commit", "-qm", "init")

    def tearDown(self):
        self.tmp.cleanup()

    def commit(self, *args):
        return run(self.repo, "bash", str(SCRIPT), *args, check=False)

    def test_commits_only_the_handoff(self):
        (self.repo / "code.txt").write_text("staged\n")
        run(self.repo, "git", "add", "code.txt")
        (self.repo / "other.txt").write_text("untracked\n")
        (self.repo / "docs").mkdir()
        (self.repo / "docs/handoff.md").write_text("# Handoff\n")

        result = self.commit("docs/handoff.md", "docs: update handoff")

        self.assertEqual(result.returncode, 0, result.stderr)
        files = run(self.repo, "git", "show", "--name-only", "--format=%s", "HEAD").stdout.split()
        self.assertEqual(files[-1], "docs/handoff.md")
        self.assertNotIn("code.txt", files)
        status = run(self.repo, "git", "status", "--short").stdout
        self.assertIn("M  code.txt", status)  # still staged, not committed
        self.assertIn("?? other.txt", status)

    def test_unchanged_file_is_a_no_op(self):
        (self.repo / "handoff.md").write_text("x\n")
        self.assertEqual(self.commit("handoff.md").returncode, 0)
        head = run(self.repo, "git", "rev-parse", "HEAD").stdout
        result = self.commit("handoff.md")
        self.assertEqual(result.returncode, 0)
        self.assertIn("nothing to commit", result.stdout)
        self.assertEqual(run(self.repo, "git", "rev-parse", "HEAD").stdout, head)

    def test_missing_file_fails(self):
        result = self.commit("nope.md")
        self.assertEqual(result.returncode, 1)


if __name__ == "__main__":
    unittest.main()

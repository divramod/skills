"""A GitHub client over recorded API answers, for the github tests (offline)."""
from __future__ import annotations

import base64
import json
from pathlib import Path

from client import GitHub, NotFound

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REPO = "kepano/defuddle"
SHA = "49d14ecc4089696565c2479b2f57db72be199adc"


def load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def repo_answers() -> dict:
    """The API answers prepare.py asks for kepano/defuddle, keyed by path."""
    readme = (FIXTURES / "README.md").read_text(encoding="utf-8")
    return {
        f"repos/{REPO}": load("repo.json"),
        f"repos/{REPO}/languages": load("languages.json"),
        f"repos/{REPO}/releases/latest": load("release.json"),
        f"repos/{REPO}/commits/main": load("commit.json"),
        f"repos/{REPO}/git/trees/{SHA}?recursive=1": load("tree.json"),
        f"repos/{REPO}/readme?ref={SHA}": {"path": "README.md",
                                           "content": base64.b64encode(readme.encode()).decode()},
        f"repos/{REPO}/git/matching-refs/heads/main": [{"ref": "refs/heads/main"}],
    }


class FakeGitHub(GitHub):
    """Answers from a table (path -> JSON, or an Exception to raise); a missing path is a 404."""

    def __init__(self, answers: dict, files: dict | None = None, mode: str = "gh"):
        self.answers, self.files, self.calls = answers, files or {}, []
        self.use_gh, self.token, self.warned = mode == "gh", None, False

    def get(self, path: str, raw: bool = False):
        self.calls.append(path)
        if path not in self.answers:
            raise NotFound(f"not found on GitHub: {path}")
        answer = self.answers[path]
        if isinstance(answer, Exception):
            raise answer
        return answer

    def graphql(self, query: str, **variables):
        return self.get("graphql:" + json.dumps(variables, sort_keys=True))

    def raw_file(self, repo: str, sha: str, path: str) -> str:
        self.calls.append(f"raw:{path}")
        if path not in self.files:
            raise NotFound(f"not found: {path}")
        return self.files[path]

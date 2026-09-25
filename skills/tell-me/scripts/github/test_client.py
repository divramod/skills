#!/usr/bin/env python3
"""Unit tests for github/client.py and github/anchors.py (offline: gh and urllib mocked)."""
import io
import json
import os
import subprocess
import sys
import unittest
import urllib.error
from email.message import Message
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import anchors  # noqa: E402
import client  # noqa: E402
from _common import MissingTool, SkillError  # noqa: E402

SHA = "49d14ecc4089696565c2479b2f57db72be199adc"


def http_error(code: int, **headers) -> urllib.error.HTTPError:
    h = Message()
    for k, v in headers.items():
        h[k.replace("_", "-")] = v
    return urllib.error.HTTPError("https://api.github.com/x", code, "err", h, io.BytesIO(b""))


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def gh_run(returncode=0, stdout="", stderr=""):
    return mock.MagicMock(return_value=subprocess.CompletedProcess(["gh"], returncode, stdout, stderr))


class TestRest(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ, {}, clear=True)
        env.start()
        self.addCleanup(env.stop)

    def test_json_and_one_rate_limit_note(self):
        gh = client.GitHub(use_gh=False)
        opened = mock.MagicMock(side_effect=lambda req, timeout: FakeResponse(b'{"full_name": "a/b"}'))
        with mock.patch("urllib.request.urlopen", opened), mock.patch.object(client, "log") as log:
            self.assertEqual(gh.get("repos/a/b"), {"full_name": "a/b"})
            gh.get("repos/a/b")
        self.assertEqual(gh.mode, "rest")
        log.assert_called_once()
        self.assertIn("60 requests/hour", log.call_args[0][0])
        req = opened.call_args[0][0]
        self.assertEqual((req.full_url, req.get_header("Authorization")), ("https://api.github.com/repos/a/b", None))

    def test_token_is_sent(self):
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "t0k"}):
            gh = client.GitHub(use_gh=False)
        opened = mock.MagicMock(return_value=FakeResponse(b"{}"))
        with mock.patch("urllib.request.urlopen", opened):
            gh.get("repos/a/b")
        self.assertEqual((gh.mode, opened.call_args[0][0].get_header("Authorization")), ("rest+token", "Bearer t0k"))

    def test_404_is_not_found(self):
        gh = client.GitHub(use_gh=False)
        with mock.patch("urllib.request.urlopen", side_effect=http_error(404)), mock.patch.object(client, "log"):
            with self.assertRaises(client.NotFound):
                gh.get("repos/a/nope")

    def test_rate_limit_names_the_reset_and_the_fix(self):
        gh = client.GitHub(use_gh=False)
        err = http_error(403, X_RateLimit_Remaining="0", X_RateLimit_Reset="1790000000")
        with mock.patch("urllib.request.urlopen", side_effect=err), mock.patch.object(client, "log"):
            with self.assertRaisesRegex(SkillError, r"rate limit reached \(resets at \d\d:\d\d\).*gh auth login"):
                gh.get("repos/a/b")

    def test_get_all_pages_until_a_short_page(self):
        gh = client.GitHub(use_gh=False)
        pages = {1: list(range(100)), 2: list(range(3))}
        with mock.patch.object(gh, "get", side_effect=lambda p: pages[int(p.rsplit("=", 1)[1])]) as get:
            self.assertEqual(len(gh.get_all("repos/a/b/issues/1/comments")), 103)
        self.assertEqual(get.call_args[0][0], "repos/a/b/issues/1/comments?per_page=100&page=2")

    def test_discussions_without_gh_or_token_need_gh(self):
        gh = client.GitHub(use_gh=False)
        with mock.patch("shutil.which", return_value=None):
            with self.assertRaisesRegex(MissingTool, "gh: brew install gh"):
                gh.graphql("query { x }")


class TestGh(unittest.TestCase):
    def test_get_runs_gh_api(self):
        run = gh_run(stdout='{"a": 1}')
        with mock.patch("subprocess.run", run):
            self.assertEqual(client.GitHub(use_gh=True).get("repos/a/b"), {"a": 1})
        self.assertEqual(run.call_args[0][0], ["gh", "api", "repos/a/b"])

    def test_404_and_rate_limit(self):
        gh = client.GitHub(use_gh=True)
        with mock.patch("subprocess.run", gh_run(1, stderr="gh: Not Found (HTTP 404)")):
            with self.assertRaises(client.NotFound):
                gh.get("repos/a/nope")
        with mock.patch("subprocess.run", gh_run(1, stderr="gh: API rate limit exceeded for user (HTTP 403)")):
            with self.assertRaisesRegex(SkillError, "rate limit reached"):
                gh.get("repos/a/b")

    def test_graphql_variables_and_errors(self):
        gh = client.GitHub(use_gh=True)
        run = gh_run(stdout='{"data": {"repository": {"x": 1}}}')
        with mock.patch("subprocess.run", run):
            self.assertEqual(gh.graphql("q", owner="a", number=3), {"repository": {"x": 1}})
        self.assertEqual(run.call_args[0][0][-4:], ["-f", "owner=a", "-F", "number=3"])
        err = json.dumps({"data": None, "errors": [{"type": "NOT_FOUND", "message": "no discussion"}]})
        with mock.patch("subprocess.run", gh_run(stdout=err)):
            with self.assertRaisesRegex(client.NotFound, "no discussion"):
                gh.graphql("q")

    def test_gh_ready_needs_a_login(self):
        with mock.patch("shutil.which", return_value="/bin/gh"), mock.patch("subprocess.run", gh_run(1)):
            self.assertFalse(client.gh_ready())
        with mock.patch("shutil.which", return_value=None):
            self.assertFalse(client.gh_ready())


class TestAnchors(unittest.TestCase):
    def test_line_anchors_heading_slugs_and_pinned_links(self):
        md = ("# Defuddle\n\nExtracts *main* content.\nSecond line.\n\n## Use it (CLI)\n\n- one\n- two\n\n"
              "```sh\n# not a heading\n```\n\n## Use it (CLI)\n\nSee [docs](docs/api.md) and ![logo](../logo.png).")
        out = anchors.anchor_file(md, "kepano/defuddle", SHA, "web/README.md")
        blob = f"https://github.com/kepano/defuddle/blob/{SHA}/web/README.md"
        self.assertIn(f"### Defuddle [#]({blob}#defuddle)", out)
        self.assertIn(f"[L3]({blob}?plain=1#L3) Extracts *main* content.\nSecond line.", out)
        self.assertIn(f"#### Use it (CLI) [#]({blob}#use-it-cli)", out)
        self.assertIn("#use-it-cli-1)", out)  # a repeated heading gets GitHub's -1
        self.assertIn(f"- [L8]({blob}?plain=1#L8) one\n- [L9]({blob}?plain=1#L9) two", out)
        self.assertIn("```sh\n# not a heading\n```", out)
        self.assertIn(f"[docs](https://github.com/kepano/defuddle/blob/{SHA}/web/docs/api.md)", out)
        self.assertIn(f"![logo](https://raw.githubusercontent.com/kepano/defuddle/{SHA}/logo.png)", out)

    def test_absolute_and_fragment_links_are_left_alone(self):
        md = "[a](https://x.dev/a) [b](#usage) [c](mailto:x@y.z)"
        self.assertEqual(anchors.absolutize(md, "o/r", SHA, "README.md"), md)


if __name__ == "__main__":
    unittest.main()

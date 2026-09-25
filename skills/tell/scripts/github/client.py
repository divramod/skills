#!/usr/bin/env python3
"""GitHub API access for the github source: `gh api` when gh is installed and logged in (5000 requests/hour,
GraphQL for discussions), else the REST API over urllib (GITHUB_TOKEN when set, else unauthenticated: 60
requests/hour, which the first request says). A rate limit or a missing item raises SkillError with the reason.

Usage: client.py <api path>   (prints the JSON, e.g. client.py repos/astral-sh/uv)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

from _common import SkillError, log, require, run_main

HOST = "github.com"
API = "https://api.github.com/"
RAW = "https://raw.githubusercontent.com/"
TIMEOUT = 60
PER_PAGE = 100


class NotFound(SkillError):
    """HTTP 404: the repo, issue or file does not exist (or is private)."""


class GitHub:
    def __init__(self, use_gh: bool | None = None):
        self.use_gh = gh_ready() if use_gh is None else use_gh
        self.token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        self.warned = False

    @property
    def mode(self) -> str:
        return "gh" if self.use_gh else "rest+token" if self.token else "rest"

    # ------------------------------------------------------------ requests

    def get(self, path: str, raw: bool = False):
        """GET an API path (`repos/o/r`); JSON, or the text when `raw`."""
        if self.use_gh:
            return self._gh(["api", path, *(["-H", "Accept: application/vnd.github.raw"] if raw else [])], raw)
        if not self.token and not self.warned:
            log("GitHub API without gh or GITHUB_TOKEN: 60 requests/hour (install gh and run `gh auth login`)")
            self.warned = True
        headers = {"Accept": "application/vnd.github.raw" if raw else "application/vnd.github+json",
                   "User-Agent": "tell", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        body = http(API + path, headers)
        return body if raw else json.loads(body)

    def get_all(self, path: str, max_pages: int = 10) -> list:
        """Every item of a list endpoint, page by page (at most max_pages * 100)."""
        items: list = []
        sep = "&" if "?" in path else "?"
        for page in range(1, max_pages + 1):
            batch = self.get(f"{path}{sep}per_page={PER_PAGE}&page={page}")
            items += batch
            if len(batch) < PER_PAGE:
                return items
        log(f"{path}: stopped after {len(items)} items")
        return items

    def graphql(self, query: str, **variables):
        """A GraphQL query (discussions have no REST API): needs gh, or GITHUB_TOKEN."""
        if self.use_gh:
            args = ["api", "graphql", "-f", f"query={query}"]
            for k, v in variables.items():
                args += ["-F" if isinstance(v, int) else "-f", f"{k}={v}"]
            data = self._gh(args)
        elif self.token:
            req = json.dumps({"query": query, "variables": variables}).encode()
            data = json.loads(http(API + "graphql", {"Authorization": f"Bearer {self.token}",
                                                    "User-Agent": "tell"}, req))
        else:
            require("gh")  # exit 2 names the installer
            raise SkillError("GitHub discussions need gh: run `gh auth login`")
        if data.get("errors"):
            msg = "; ".join(e.get("message", "?") for e in data["errors"])
            if any(e.get("type") == "NOT_FOUND" or "Could not resolve to" in e.get("message", "")
                   for e in data["errors"]):
                raise NotFound(msg)
            raise SkillError(f"GitHub GraphQL: {msg}")
        return data["data"]

    def raw_file(self, repo: str, sha: str, path: str) -> str:
        """A file's text at a commit. gh: the contents API (its login reaches private repos); else
        raw.githubusercontent.com (no API rate limit), with the token when set (private repos need it)."""
        quoted = urllib.parse.quote(path)
        if self.use_gh:
            return self.get(f"repos/{repo}/contents/{quoted}?ref={sha}", raw=True)
        headers = {"User-Agent": "tell"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return http(f"{RAW}{repo}/{sha}/{quoted}", headers)

    def _gh(self, args: list[str], raw: bool = False):
        # --hostname: github.com even when GH_HOST points gh at a GitHub Enterprise server
        cmd = ["gh", args[0], "--hostname", HOST, *args[1:]]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            raise SkillError(f"gh {args[1]} timed out after {TIMEOUT}s")
        if p.returncode != 0:
            err = (p.stderr.strip() or p.stdout.strip()).splitlines()
            msg = err[-1] if err else f"gh exited {p.returncode}"
            # GraphQL answers a missing discussion or repo with "Could not resolve to a Discussion ..."
            if "HTTP 404" in msg or "Not Found" in msg or "Could not resolve to" in msg:
                raise NotFound(f"not found on GitHub: {args[1]} ({msg})")
            if "rate limit" in msg.lower():
                raise SkillError(f"GitHub rate limit reached ({msg}); wait for the reset (`gh api rate_limit`)")
            raise SkillError(f"gh api {args[1]}: {msg}")
        return p.stdout if raw else json.loads(p.stdout or "null")


def gh_ready() -> bool:
    """gh installed and logged in."""
    if not shutil.which("gh"):
        return False
    try:
        return subprocess.run(["gh", "auth", "token", "--hostname", HOST], capture_output=True,
                              timeout=15).returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def http(url: str, headers: dict, data: bytes | None = None) -> str:
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise NotFound(f"not found on GitHub: {url}")
        if e.code in (403, 429) and e.headers.get("X-RateLimit-Remaining") == "0":
            reset = e.headers.get("X-RateLimit-Reset")
            at = datetime.fromtimestamp(int(reset)).strftime("%H:%M") if reset and reset.isdigit() else "later"
            raise SkillError(f"GitHub rate limit reached (resets at {at}); install gh and run `gh auth login`, "
                             f"or set GITHUB_TOKEN, for 5000 requests/hour")
        raise SkillError(f"GitHub answered HTTP {e.code} for {url}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise SkillError(f"could not reach GitHub ({url}): {getattr(e, 'reason', e)}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="API path, e.g. repos/astral-sh/uv")
    args = ap.parse_args(argv)
    gh = GitHub()
    log(f"api: {gh.mode}")
    print(json.dumps(gh.get(args.path), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    run_main(main)

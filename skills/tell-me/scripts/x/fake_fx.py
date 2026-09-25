"""A FxTwitter client over recorded API answers, for the x tests (offline)."""
from __future__ import annotations

import json
from pathlib import Path

from _common import SkillError
from client import FX, FxTwitter

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ROOT = "2102861892549279922"  # simonw: a two-post thread with replies
SECOND = "2102861969472807418"  # its second post
VIDEO = "2083749667410727319"  # karpathy: a post with a video
NOT_FOUND = {"status": None, "thread": None, "author": None, "code": 404}


def load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def answers() -> dict:
    """The recorded answers, keyed by URL."""
    thread = load("thread.json")
    video = load("status.video.json")
    return {
        f"{FX}thread/{ROOT}": thread,
        # FxTwitter's thread of a post inside a self-thread starts at that post
        f"{FX}thread/{SECOND}": thread | {"status": thread["thread"][1], "thread": thread["thread"][1:]},
        f"{FX}conversation/{ROOT}?ranking_mode=likes": load("conversation.likes.json"),
        f"{FX}conversation/{ROOT}?ranking_mode=recency": load("conversation.recency.json"),
        f"{FX}thread/{VIDEO}": video | {"thread": [video["status"]]},
        f"{FX}conversation/{VIDEO}?ranking_mode=likes": video | {"replies": [], "cursor": None},
        f"{FX}conversation/{VIDEO}?ranking_mode=recency": video | {"replies": [], "cursor": None},
    }


class FakeGet:
    """url -> recorded answer; unknown URLs answer FxTwitter's 404 (or raise, for the embed endpoint).
    `calls` records every URL."""

    def __init__(self, extra: dict | None = None):
        self.answers = answers() | (extra or {})
        self.calls: list[str] = []

    def __call__(self, url: str) -> dict:
        self.calls.append(url)
        if "&cursor=" in url and url not in self.answers:
            return {"code": 404}  # FxTwitter 404s its own cursors (2026-09)
        answer = self.answers.get(url)
        if isinstance(answer, Exception):
            raise answer
        if answer is None:
            if "syndication" in url:
                raise SkillError(f"{url} answered HTTP 404")
            return dict(NOT_FOUND)
        return answer() if callable(answer) else answer


def fake(extra: dict | None = None) -> FxTwitter:
    return FxTwitter(get=FakeGet(extra))

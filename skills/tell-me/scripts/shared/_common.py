"""Shared helpers for the tell-me scripts. Stdlib only.

Library layout: <root>/<platform>/<user>/<title-slug>/ with summary.md, transcript.md,
metadata.json, video.<ext>, frames/. Root: $DM_SUMMARIZE_VIDEO_ROOT or ~/me/summaries/videos.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import unicodedata
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
INSTALL_SCRIPT = SCRIPTS_DIR / "install-prerequisites.sh"
INSTALL_HINTS = {
    "yt-dlp": "brew install yt-dlp",
    "ffmpeg": "brew install ffmpeg",
    "ffprobe": "brew install ffmpeg",
    "uvx": "brew install uv",
}
BOT_HINT = (
    "YouTube bot check / rate limit hit. Retry with --cookies-from-browser chrome "
    "(or firefox/safari), wait a few minutes, or upgrade yt-dlp: "
    f"{INSTALL_SCRIPT} --upgrade"
)


class SkillError(RuntimeError):
    """Expected failure: message is shown to the user, script exits 1."""


class MissingTool(SkillError):
    """A required external tool is not on PATH: script exits 2."""


def log(msg: str) -> None:
    print(f"[tell-me] {msg}", file=sys.stderr)


def library_root() -> Path:
    return Path(os.environ.get("DM_SUMMARIZE_VIDEO_ROOT", Path.home() / "me" / "summaries" / "videos")).expanduser()


def require(*tools: str) -> None:
    """Fail with a clear message when an external tool is missing."""
    missing = [t for t in tools if not shutil.which(t)]
    if missing:
        hints = "\n".join(f"  {t}: {INSTALL_HINTS.get(t, 'install it and put it on PATH')}" for t in missing)
        raise MissingTool(
            f"missing required tool(s): {', '.join(missing)}\n{hints}\n"
            f"or run: {INSTALL_SCRIPT}"
        )


def run_main(main) -> None:
    """Run a script's main(), mapping expected errors to exit codes."""
    try:
        sys.exit(main())
    except MissingTool as e:
        log(str(e))
        sys.exit(2)
    except SkillError as e:
        log(str(e))
        sys.exit(1)


# ---------------------------------------------------------------- naming


def slugify(text: str | None, max_len: int = 80) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return text[:max_len].rstrip("-") or "untitled"


def platform_of(info: dict) -> str:
    key = (info.get("extractor_key") or info.get("extractor") or "video").lower()
    return "youtube" if key.startswith("youtube") else slugify(key.split(":")[0])


def user_of(info: dict) -> str:
    for key in ("uploader_id", "channel", "uploader", "channel_id"):
        val = info.get(key)
        if val:
            return slugify(str(val).lstrip("@"))
    return "unknown"


def video_dir(info: dict, root: Path | None = None) -> Path:
    root = root or library_root()
    return root / platform_of(info) / user_of(info) / slugify(info.get("title"))


def find_existing(info: dict, root: Path | None = None) -> Path | None:
    """Folder of an already-prepared video with the same platform + id (title may have changed)."""
    root = root or library_root()
    vid = info.get("id")
    base = root / platform_of(info)
    if not vid or not base.is_dir():
        return None
    for meta in base.glob("*/*/metadata.json"):
        try:
            if json.loads(meta.read_text()).get("id") == vid:
                return meta.parent
        except (OSError, json.JSONDecodeError):
            continue
    return None


# ---------------------------------------------------------------- time + links


def fmt_ts(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def parse_ts(ts: str) -> float:
    secs = 0.0
    for part in ts.replace(",", ".").split(":"):
        secs = secs * 60 + float(part)
    return secs


def ts_url(info: dict, seconds: float) -> str | None:
    """Deep link to a moment, or None when the platform has no known scheme."""
    s = int(seconds)
    if platform_of(info) == "youtube" and info.get("id"):
        return f"https://www.youtube.com/watch?v={info['id']}&t={s}s"
    if platform_of(info) == "vimeo" and info.get("webpage_url"):
        return f"{info['webpage_url'].split('#')[0]}#t={s}s"
    return None


def ts_link(info: dict, seconds: float) -> str:
    url = ts_url(info, seconds)
    return f"[{fmt_ts(seconds)}]({url})" if url else fmt_ts(seconds)


# ---------------------------------------------------------------- io


def ytdlp_base(cookies_from_browser: str | None = None) -> list[str]:
    cmd = ["yt-dlp", "--no-playlist", "--no-warnings"]
    if cookies_from_browser:
        cmd += ["--cookies-from-browser", cookies_from_browser]
    return cmd


def is_bot_error(stderr: str) -> bool:
    return bool(re.search(r"not a bot|HTTP Error 429|Sign in to confirm", stderr))


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_json(path: Path, data: dict) -> None:
    """Atomic write: the background video download and the foreground scripts share metadata.json."""
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def update_json(path: Path, fields: dict) -> dict:
    """Merge fields into a JSON file (read-modify-write) and return the result."""
    data = read_json(path) | fields
    write_json(path, data)
    return data


def probe_duration(media: Path) -> float | None:
    """Media duration in seconds via ffprobe, or None."""
    require("ffprobe")
    import subprocess
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(media)],
                       capture_output=True, text=True)
    try:
        return float(p.stdout.strip())
    except ValueError:
        return None


_PARTIAL_RE = re.compile(r"\.(part|ytdl|temp|tagging)\b|\.f\d+\.")


def find_file(folder: Path, stem: str) -> Path | None:
    """First finished `<stem>.<ext>` in folder.

    Ignores yt-dlp work files: `.part`/`.ytdl`, the `.temp.<ext>` merge target and the
    per-format `.f<id>.<ext>` streams that exist until video and audio are merged.
    """
    for f in sorted(folder.glob(f"{stem}.*")):
        if not _PARTIAL_RE.search(f.name[len(stem):]):
            return f
    return None


# ---------------------------------------------------------------- agent

# (env var, agent name) checked in order; AI_AGENT is the cross-tool convention and wins.
AGENT_ENV = (
    ("CLAUDECODE", "claude-code"),
    ("CODEX_THREAD_ID", "codex"),
    ("CODEX_SANDBOX", "codex"),
    ("CODEX_MANAGED_BY_NPM", "codex"),
    ("GROK_CLI", "grok"),
    ("GEMINI_CLI", "gemini-cli"),
    ("OPENCODE", "opencode"),
    ("CURSOR_AGENT", "cursor"),
    ("COPILOT_CLI", "copilot"),
)


def detect_agent(env: dict | None = None) -> str | None:
    """Name (+ version when known) of the agentic CLI running this script, or None.

    `AI_AGENT=claude-code_2-1-282_agent` -> "claude-code 2.1.282".
    """
    env = os.environ if env is None else env
    ai = env.get("AI_AGENT", "").strip()
    if ai:
        m = re.fullmatch(r"(.+?)_(\d+(?:-\d+)*)(?:_agent)?", ai)
        return f"{m.group(1)} {m.group(2).replace('-', '.')}" if m else ai.removesuffix("_agent")
    for var, name in AGENT_ENV:
        if env.get(var):
            return name
    return None

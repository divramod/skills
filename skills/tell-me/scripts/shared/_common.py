"""Shared helpers for the tell-me scripts. Stdlib only.

Library layout: <root>/<kind>/.../ per source (see dir_for), each folder with summary.md,
metadata.json and the content file; <root>/library.js indexes them all. Root: $TELL_ME_ROOT, else
the parent of $DM_SUMMARIZE_VIDEO_ROOT (the old videos-only root), else ~/me/summaries.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import unicodedata
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent  # scripts/shared
SKILL_DIR = SCRIPTS_DIR.parent.parent
INSTALL_HINTS = {
    "yt-dlp": "brew install yt-dlp",
    "ffmpeg": "brew install ffmpeg",
    "ffprobe": "brew install ffmpeg",
    "uvx": "brew install uv",
    "npx": "brew install node",
    "gh": "brew install gh",
    "pdftotext": "brew install poppler",
    "pandoc": "brew install pandoc",
}
BOT_HINT = (
    "YouTube bot check / rate limit hit. Retry with --cookies-from-browser chrome "
    "(or firefox/safari), wait a few minutes, or upgrade yt-dlp: "
    f"{SCRIPTS_DIR.parent / 'video' / 'install-prerequisites.sh'} --upgrade"
)


class SkillError(RuntimeError):
    """Expected failure: message is shown to the user, script exits 1."""


class MissingTool(SkillError):
    """A required external tool is not on PATH: script exits 2."""


def log(msg: str) -> None:
    print(f"[tell-me] {msg}", file=sys.stderr)


# Top-level library folder per source.
KIND_DIRS = {"video": "videos", "web": "articles", "github": "repos", "x": "posts", "hn": "discussions",
             "file": "documents"}


def library_root() -> Path:
    if os.environ.get("TELL_ME_ROOT"):
        return Path(os.environ["TELL_ME_ROOT"]).expanduser()
    old = os.environ.get("DM_SUMMARIZE_VIDEO_ROOT")
    if old:  # the videos-only root of earlier versions: <root>/videos
        videos = Path(old).expanduser()
        if videos.name != KIND_DIRS["video"]:
            raise SkillError(f"DM_SUMMARIZE_VIDEO_ROOT={old} is not a folder named 'videos'. tell-me now keeps every "
                             f"source under one root: set TELL_ME_ROOT to that root and move the videos into "
                             f"<root>/videos (then run scripts/video/migrate_library.py --apply)")
        return videos.parent
    return Path.home() / "me" / "summaries"


def source_root(source: str, root: Path | None = None) -> Path:
    return (root or library_root()) / KIND_DIRS[source]


def install_script(script: str | None = None) -> Path:
    """install-prerequisites.sh of the running script's source folder (scripts/<source>/), else the aggregator."""
    folder = Path(script or sys.argv[0]).resolve().parent
    own = folder / "install-prerequisites.sh"
    if folder.parent == SCRIPTS_DIR.parent and own.is_file():
        return own
    return SCRIPTS_DIR.parent / "install-prerequisites.sh"


def require(*tools: str) -> None:
    """Fail with a clear message (exit 2) when an external tool is missing; names the source's installer."""
    missing = [t for t in tools if not shutil.which(t)]
    if missing:
        hints = "\n".join(f"  {t}: {INSTALL_HINTS.get(t, 'install it and put it on PATH')}" for t in missing)
        raise MissingTool(
            f"missing required tool(s): {', '.join(missing)}\n{hints}\n"
            f"or run: {install_script()}"
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
    """<root>/videos/<platform>/<user>/<title-slug>; `root` is the videos folder when given."""
    root = root or source_root("video")
    return root / platform_of(info) / user_of(info) / slugify(info.get("title"))


def dir_for(meta: dict, root: Path | None = None) -> Path:
    """Library folder for a source's metadata (contract fields; video uses its yt-dlp keys).

    video   videos/<platform>/<channel>/<title>          web    articles/<site>/<title>
    github  repos/github/<owner>/<repo>[/<kind>s/<n>-<title>]
    x       posts/x/<user>/<first-words>-<id>            hn     discussions/hn/<title>-<id>
    file    documents/<parent-folder>/<file-stem> (a URL: documents/<host>/<file-stem>)
    """
    source = meta.get("source") or "video"
    base = source_root(source, root)
    extras = meta.get("extras") or {}
    title = meta.get("title")
    if source == "video":
        return video_dir(meta, base)
    if source == "web":
        return base / slugify(meta.get("site") or host_slug(meta.get("url"))) / slugify(title)
    if source == "github":
        repo, _, number = str(meta.get("id") or "unknown/unknown").partition("#")
        owner, _, name = repo.partition("/")
        folder = base / "github" / slugify(owner) / slugify(name)
        return folder / f"{extras.get('kind', 'issue')}s" / f"{number}-{slugify(title, 60)}" if number else folder
    if source == "x":
        user = extras.get("user") or meta.get("author")
        return base / "x" / slugify(str(user or "unknown").lstrip("@")) / f"{slugify(title, 40)}-{meta['id']}"
    if source == "hn":
        return base / "hn" / f"{slugify(title, 60)}-{meta['id']}"
    if source == "file":
        url = meta.get("url") or ""
        if extras.get("original_path") or not url.startswith(("http://", "https://")):
            path = Path(extras.get("original_path") or url.removeprefix("file://") or "unknown")
            return base / slugify(path.parent.name or "root") / slugify(path.stem)
        name = extras.get("file_name") or url.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
        return base / slugify(host_slug(url)) / slugify(Path(name).stem or name)
    raise ValueError(f"unknown source {source!r}")


def unique_dir(meta: dict, root: Path | None = None) -> Path:
    """dir_for(), plus a short hash of the id when that folder already holds a different item
    (two pages titled "Home" on one site, two notes/x.pdf in different folders)."""
    folder = dir_for(meta, root)
    other = read_json(folder / "metadata.json").get("id")
    if other and other != meta.get("id"):
        folder = folder.with_name(f"{folder.name}-{hashlib.sha1(str(meta.get('id')).encode()).hexdigest()[:6]}")
    return folder


def digest_dir(items: list[dict], day: str, root: Path | None = None, folder: Path | None = None,
               **fields) -> Path:
    """The folder of a digest across items (a playlist's videos, several inputs) with its metadata.json
    (kind: digest, items). Default folder: <root>/digests/<day>-<slug of the titles>/; the same items on the
    same day reuse it."""
    titles = [str(i.get("title") or "untitled") for i in items]
    title = fields.pop("title", None) or (" · ".join(titles) if len(titles) <= 3 else
                                         f"{' · '.join(titles[:2])} and {len(titles) - 2} more")
    if folder is None:
        slug = slugify(titles[0], 40) + (f"-and-{len(titles) - 1}-more" if len(titles) > 1 else "")
        folder = (root or library_root()) / "digests" / f"{day}-{slug}"
        ids = [i.get("dir") or i.get("url") for i in items]
        if (old := read_json(folder / "metadata.json")) and [i.get("dir") or i.get("url") for i in
                                                             old.get("items") or []] != ids:
            folder = folder.with_name(f"{folder.name}-{hashlib.sha1(repr(ids).encode()).hexdigest()[:6]}")
    folder.mkdir(parents=True, exist_ok=True)
    # merge: a saved digest's `summary` record stays
    update_json(folder / "metadata.json", {"kind": "digest", "title": title, "created": day, "items": items} | fields)
    return folder


def host_slug(url: str | None) -> str:
    host = re.sub(r"^https?://", "", url or "").split("/")[0].split(":")[0]
    return re.sub(r"^www\.", "", host) or "unknown"


def find_by_id(source: str, id_: str | None, root: Path | None = None) -> Path | None:
    """Folder of an already-prepared item of this source with the same id (its title may have changed), or with
    that id among its `extras.aliases` (e.g. a web page's short link or pre-redirect URL)."""
    base = source_root(source, root)
    if not id_ or not base.is_dir():
        return None
    for meta in base.rglob("metadata.json"):
        data = read_json(meta)
        known = data.get("id") == id_ or id_ in ((data.get("extras") or {}).get("aliases") or [])
        if known and (data.get("source") or "video") == source and data.get("kind") != "digest":
            return meta.parent
    return None


def find_existing(info: dict, root: Path | None = None) -> Path | None:
    """Folder of an already-prepared video with the same platform + id (title may have changed).
    `root` is the videos folder when given."""
    root = root or source_root("video")
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


# ---------------------------------------------------------------- source contract

# Shared metadata.json fields every source writes (G2); per-source data goes into `extras`.
CONTRACT_KEYS = ("source", "id", "url", "title", "author", "published", "fetched", "site", "word_count",
                 "duration", "extractor", "content_file", "extras")
# Keys every scripts/<source>/prepare.py prints (plus its own extras).
ENVELOPE_KEYS = ("source", "kind", "dir", "id", "title", "url", "content_file", "summary", "summary_exists",
                 "subskill", "template")


def fmt_date(value: str | None) -> str | None:
    """yt-dlp's 20260924 -> 2026-09-24; ISO dates pass through."""
    if value and re.fullmatch(r"\d{8}", value):
        return f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return value


def is_legacy(meta: dict) -> bool:
    """metadata.json of a video folder written before the source contract (see video/migrate_library.py)."""
    return bool(meta) and "source" not in meta and meta.get("kind") != "digest"


def contract(meta: dict) -> dict:
    """The contract fields of a metadata.json. Video folders written before the contract are mapped
    from their yt-dlp keys, so shared code reads only these fields."""
    digest = meta.get("kind") == "digest"
    legacy = {
        "source": None if digest else "video",
        "id": meta.get("id"),
        "url": meta.get("webpage_url"),
        "title": meta.get("title"),
        "author": meta.get("channel") or meta.get("uploader") or meta.get("user"),
        "published": fmt_date(meta.get("upload_date")),
        "fetched": meta.get("prepared_at") or meta.get("prepared"),
        "site": meta.get("platform"),
        "duration": meta.get("duration"),
        "extractor": meta.get("transcript_source"),
        "content_file": None if digest else "content.md",
        "extras": {},
    }
    return {k: meta[k] if meta.get(k) not in (None, "") else legacy.get(k) for k in CONTRACT_KEYS}


def subskill_path(source: str) -> Path:
    return SKILL_DIR / "subskills" / source / "SUBSKILL.md"


def template_path(source: str) -> Path:
    return SKILL_DIR / "templates" / source / "template.md"


def envelope(folder: Path, meta: dict, kind: str, **extras) -> dict:
    """The JSON a source's prepare.py prints: the ENVELOPE_KEYS, then the source's extras."""
    c = contract(meta)
    content = folder / c["content_file"] if c["content_file"] else None
    summary = folder / "summary.md"
    out = {
        "source": c["source"], "kind": kind, "dir": str(folder), "id": c["id"], "title": c["title"], "url": c["url"],
        "author": c["author"], "published": c["published"],
        "content_file": str(content) if content else None,
        "content_words": len(content.read_text(encoding="utf-8").split()) if content and content.exists() else 0,
        "summary": str(summary), "summary_exists": summary.exists(),
        "subskill": str(subskill_path(c["source"])), "template": str(template_path(c["source"])),
    }
    return out | extras


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


def update_json(path: Path, fields: dict, drop: tuple[str, ...] = ()) -> dict:
    """Merge fields into a JSON file (read-modify-write), remove the `drop` keys, and return the result."""
    data = {k: v for k, v in (read_json(path) | fields).items() if k not in drop}
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

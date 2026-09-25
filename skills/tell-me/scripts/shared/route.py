#!/usr/bin/env python3
"""Classify an input (URL or local path) into exactly one tell-me source. No network.

  video   YouTube (video / playlist / channel), youtu.be, Vimeo, TikTok, Twitch, podcasts,
          any other host in VIDEO_HOSTS, and direct media files (.mp4, .mp3, ...)
  x       x.com / twitter.com / fixupx / fxtwitter / vxtwitter posts (…/status/<id>)
  hn      news.ycombinator.com/item?id=<id>
  github  github.com/<owner>/<repo>[/tree|blob/…]; /issues/N, /pull/N, /discussions/N
  file    a local path (absolute, ~, relative, file://) or a document URL (.pdf, .docx, .epub, …)
  web     any other http(s) URL

Prints one JSON object: {source, kind, id, url} (or `path` instead of `url` for local files).
`id` is the dedupe key inside the source. Unknown schemes and missing local files exit 1.

Usage: route.py "<url-or-path>"
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlencode, urlsplit, urlunsplit

from _common import SkillError, run_main

SOURCES = ("video", "web", "github", "x", "hn", "file")

# Hosts whose pages are videos/audio for yt-dlp (matched with any subdomain).
VIDEO_HOSTS = (
    "youtube.com", "youtu.be", "youtube-nocookie.com", "vimeo.com", "tiktok.com", "twitch.tv", "dailymotion.com",
    "dai.ly", "rumble.com", "bilibili.com", "b23.tv", "soundcloud.com", "mixcloud.com", "bandcamp.com",
    "podcasts.apple.com", "open.spotify.com", "ted.com", "loom.com", "streamable.com", "odysee.com",
    "bitchute.com", "nebula.tv", "peertube.tv", "archive.org", "facebook.com/watch", "fb.watch",
    "instagram.com/reel", "instagram.com/p", "reddit.com/link", "v.redd.it", "kick.com", "vk.com/video",
    "nicovideo.jp", "coub.com", "wistia.com", "vidyard.com", "media.ccc.de", "infoq.com/presentations",
)
MEDIA_EXT = {".mp4", ".m4v", ".mkv", ".webm", ".mov", ".avi", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav",
             ".flac", ".m3u8"}
DOC_EXT = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".epub", ".odt", ".rtf", ".md", ".txt",
           ".html", ".htm", ".csv", ".json", ".xml", ".ipynb", ".tex", ".rst", ".org"}
# Document URLs that go to the file source (a remote .md/.html/.txt is just a web page).
REMOTE_DOC_EXT = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".epub", ".odt", ".rtf", ".ipynb"}
X_HOSTS = {"x.com", "twitter.com", "fixupx.com", "fxtwitter.com", "vxtwitter.com", "fixvx.com", "nitter.net",
           "xcancel.com"}
# github.com/<first segment> that are not owners.
GITHUB_RESERVED = {"about", "apps", "blog", "collections", "contact", "customer-stories", "enterprise", "events",
                   "explore", "features", "issues", "login", "marketplace", "new", "notifications", "orgs",
                   "organizations", "pricing", "pulls", "search", "security", "settings", "signup", "site",
                   "sponsors", "topics", "trending", "codespaces", "copilot", "readme", "team"}
TRACKING_PARAMS = re.compile(r"^(utm_\w+|fbclid|gclid|mc_cid|mc_eid|ref_src|ref_url|si|igshid)$")
_BARE_HOST_RE = re.compile(r"^[\w-]+(\.[\w-]+)*\.[a-z]{2,}(:\d+)?(/|\?|$)", re.I)
_YT_ID_RE = re.compile(r"^[\w-]{11}$")


def host_of(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return re.sub(r"^(www|m|mobile)\.", "", host)


def host_matches(host: str, path: str, patterns) -> bool:
    for pat in patterns:
        dom, _, prefix = pat.partition("/")
        if (host == dom or host.endswith("." + dom)) and (not prefix or path.startswith("/" + prefix)):
            return True
    return False


def clean_url(url: str) -> str:
    """Canonical form for dedupe: https, lowercase host without www., no fragment, no tracking params."""
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qs(parts.query, keep_blank_values=True).items() if not TRACKING_PARAMS.match(k)]
    q = urlencode([(k, x) for k, vs in query for x in vs])
    path = parts.path if parts.path not in ("", "/") else "/"
    return urlunsplit(("https" if parts.scheme in ("http", "https") else parts.scheme, host_of(url) + (
        f":{parts.port}" if parts.port else ""), path, q, ""))


# ---------------------------------------------------------------- per source


def youtube(url: str, host: str, path: str, query: dict) -> dict:
    segs = [s for s in path.split("/") if s]
    vid = None
    if host == "youtu.be" and segs:
        vid = segs[0]
    elif query.get("v"):
        vid = query["v"][0]
    elif len(segs) >= 2 and segs[0] in ("shorts", "live", "embed", "v"):
        vid = segs[1]
    if vid and _YT_ID_RE.match(vid):
        return {"kind": "video", "id": vid, "url": f"https://www.youtube.com/watch?v={vid}"}
    if query.get("list"):
        lid = query["list"][0]
        return {"kind": "playlist", "id": lid, "url": f"https://www.youtube.com/playlist?list={lid}"}
    if segs and (segs[0].startswith("@") or segs[0] in ("channel", "c", "user")):
        name = segs[0] if segs[0].startswith("@") else "/".join(segs[:2])
        return {"kind": "channel", "id": name, "url": f"https://www.youtube.com/{name}"}
    return {"kind": "video", "id": clean_url(url), "url": url}


def github(host: str, segs: list[str]) -> dict | None:
    if host != "github.com" or len(segs) < 2 or segs[0].lower() in GITHUB_RESERVED:
        return None
    owner, repo = segs[0], re.sub(r"\.git$", "", segs[1])
    base = f"https://github.com/{owner}/{repo}"
    rest = segs[2:]
    kinds = {"issues": "issue", "pull": "pull", "pulls": "pull", "discussions": "discussion"}
    if len(rest) >= 2 and rest[0] in kinds and rest[1].isdigit():
        kind = kinds[rest[0]]
        seg = "pull" if kind == "pull" else rest[0]
        return {"kind": kind, "id": f"{owner}/{repo}#{rest[1]}", "url": f"{base}/{seg}/{rest[1]}",
                "repo": f"{owner}/{repo}", "number": int(rest[1])}
    out = {"kind": "repo", "id": f"{owner}/{repo}", "url": base, "repo": f"{owner}/{repo}"}
    if len(rest) >= 2 and rest[0] in ("tree", "blob"):
        out |= {"ref": rest[1], "path": "/".join(rest[2:])}
        if rest[0] == "blob":
            out |= {"kind": "blob", "url": f"{base}/blob/{'/'.join(rest[1:])}"}
    return out


def x_post(host: str, segs: list[str]) -> dict | None:
    if host not in X_HOSTS:
        return None
    # /<user>/status/<id>[/photo/1], /i/web/status/<id>, /i/status/<id>
    for i, s in enumerate(segs[:-1]):
        if s in ("status", "statuses") and segs[i + 1].isdigit():
            user = segs[0] if i == 1 else None
            post = segs[i + 1]
            url = f"https://x.com/{user}/status/{post}" if user and user != "i" else f"https://x.com/i/status/{post}"
            return {"kind": "post", "id": post, "url": url, **({"user": user} if user and user != "i" else {})}
    raise SkillError(f"x/twitter: only post URLs are supported (…/status/<id>), got {'/'.join(segs) or 'the home page'}")


def local_file(text: str, cwd: Path) -> dict:
    raw = unquote(urlsplit(text).path) if text.startswith("file://") else text
    path = (cwd / Path(raw).expanduser()).resolve() if not Path(raw).expanduser().is_absolute() \
        else Path(raw).expanduser().resolve()
    if not path.exists():
        raise SkillError(f"no such file: {path}")
    if path.is_dir():
        raise SkillError(f"{path} is a folder: pass a document inside it")
    kind = path.suffix.lower().lstrip(".") or "file"
    if path.suffix.lower() in MEDIA_EXT:
        return {"source": "video", "kind": "media", "id": str(path), "path": str(path)}
    return {"source": "file", "kind": kind, "id": str(path), "path": str(path)}


def looks_local(text: str, cwd: Path) -> bool:
    if text.startswith(("file://", "/", "~", "./", "../")) or re.match(r"^[A-Za-z]:\\", text):
        return True
    if "://" in text:
        return False
    if (cwd / text).expanduser().exists():
        return True
    # "notes.pdf" is a (missing) file; "example.com/paper.pdf" is a URL without a scheme.
    return Path(text).suffix.lower() in DOC_EXT | MEDIA_EXT and ("/" not in text or not _BARE_HOST_RE.match(text))


def route(text: str, cwd: Path | None = None) -> dict:
    """{source, kind, id, url|path, ...} for one input; SkillError when it can't be classified."""
    text = text.strip().strip("<>\"'")
    cwd = cwd or Path.cwd()
    if not text:
        raise SkillError("empty input")
    if looks_local(text, cwd):
        return local_file(text, cwd)
    if "://" not in text and _BARE_HOST_RE.match(text):
        text = "https://" + text
    parts = urlsplit(text)
    if parts.scheme not in ("http", "https"):
        raise SkillError(f"unsupported input {text!r}: pass an http(s) URL or a local file path")
    host, path = host_of(text), parts.path
    query = parse_qs(parts.query)
    segs = [s for s in path.split("/") if s]
    suffix = Path(path).suffix.lower()

    if host_matches(host, path, ("youtube.com", "youtu.be", "youtube-nocookie.com")):
        return {"source": "video"} | youtube(text, host, path, query)
    if host == "news.ycombinator.com" and path == "/item" and query.get("id", [""])[0].isdigit():
        hid = query["id"][0]
        return {"source": "hn", "kind": "item", "id": hid, "url": f"https://news.ycombinator.com/item?id={hid}"}
    if (x := x_post(host, segs)) is not None:
        return {"source": "x"} | x
    if (gh := github(host, segs)) is not None:
        return {"source": "github"} | gh
    if suffix in MEDIA_EXT or host_matches(host, path, VIDEO_HOSTS):
        return {"source": "video", "kind": "video", "id": clean_url(text), "url": text}
    if suffix in REMOTE_DOC_EXT:
        return {"source": "file", "kind": suffix.lstrip("."), "id": clean_url(text), "url": text}
    return {"source": "web", "kind": "page", "id": clean_url(text), "url": clean_url(text)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="URL or local file path")
    args = ap.parse_args(argv)
    print(json.dumps(route(args.input), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    run_main(main)

#!/usr/bin/env python3
"""Serve the summary library over http://127.0.0.1 so pages can embed YouTube and seek local videos.

Pages opened from file:// send no Referer, and YouTube refuses to embed without one ("Error 153").
Python's built-in http.server has no Range support, so the browser can't seek in local videos.
This server fixes both. `ensure_running()` starts it detached (pid + port in <root>/.server.json)
and returns the base URL; save_summary.py / render_html.py --open use it.

It also lets a summary page download its video (same file and quality as video/prepare.py's default download):
  GET  /api/status?path=<folder rel. to root>  -> {status: none|running|failed|done, progress, stream, error}
  POST /api/download  {"path": "<folder>"}      -> starts video/download_video.py in the background
  POST /api/delete-video {"path": "<folder>"}   -> deletes video.<ext>, refreshes summary.md/.html
The API only answers requests for this host (no DNS rebinding), and POST needs the
X-DM-Summarize header, which other sites can't send cross-origin without a CORS preflight that
this server never grants. The video URL always comes from the folder's metadata.json.

Usage: serve_library.py [--port 8765] [--root DIR]   (foreground)
       serve_library.py --ensure                     (start in the background if needed, print base URL)
       serve_library.py --stop
"""
from __future__ import annotations

import argparse
import http.server
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from _common import library_root, log, read_json, run_main, write_json

DEFAULT_PORT = int(os.environ.get("DM_SUMMARIZE_VIDEO_PORT", "8765"))
STATE_FILE = ".server.json"
_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)$")


class RangeHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler + single-range `Range: bytes=a-b` requests (206)."""

    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".mkv": "video/x-matroska", ".webm": "video/webm", ".mp4": "video/mp4", ".js": "text/javascript"}

    def log_message(self, format, *args):  # noqa: A002 (quiet)
        pass

    def send_head(self):
        path = Path(self.translate_path(self.path))
        m = _RANGE_RE.match(self.headers.get("Range", "").strip())
        if not m or not path.is_file():
            return super().send_head()
        size = path.stat().st_size
        start, end = m.group(1), m.group(2)
        if start:
            start, end = int(start), min(int(end) if end else size - 1, size - 1)
        else:  # suffix range: last N bytes
            start, end = max(size - int(end or 0), 0), size - 1
        if start >= size or start > end:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return None
        f = open(path, "rb")
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self._remaining = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        remaining = getattr(self, "_remaining", None)
        if remaining is None:
            return super().copyfile(source, outputfile)
        try:
            while remaining > 0:
                chunk = source.read(min(256 * 1024, remaining))
                if not chunk:
                    break
                outputfile.write(chunk)
                remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):  # the browser cancels ranges while seeking
            pass
        finally:
            self._remaining = None

    # ------------------------------------------------------------ api

    def _same_host(self) -> bool:
        port = self.server.server_address[1]
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        origin = self.headers.get("Origin")
        return self.headers.get("Host") in hosts and (origin is None or origin in {f"http://{h}" for h in hosts})

    def _json(self, code: int, data: dict) -> None:
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _folder(self, rel: str | None) -> Path | None:
        """A video folder inside the served root, or None."""
        if not rel:
            return None
        root = Path(self.directory).resolve()
        folder = (root / rel).resolve()
        try:
            folder.relative_to(root)
        except ValueError:
            return None
        meta = read_json(folder / "metadata.json")
        return folder if meta and meta.get("kind") != "digest" and meta.get("webpage_url") else None

    def _api(self, method: str) -> None:
        if not self._same_host():
            return self._json(403, {"error": "forbidden"})
        route = urlsplit(self.path).path
        if method == "GET" and route == "/api/status":
            folder = self._folder(parse_qs(urlsplit(self.path).query).get("path", [None])[0])
            return self._json(200, video_state(folder)) if folder else self._json(404, {"error": "unknown folder"})
        if method == "POST" and route in ("/api/download", "/api/delete-video"):
            if self.headers.get("X-DM-Summarize") != "1":
                return self._json(403, {"error": "missing X-DM-Summarize header"})
            try:
                length = min(int(self.headers.get("Content-Length") or 0), 4096)
                rel = json.loads(self.rfile.read(length) or b"{}").get("path")
            except (ValueError, AttributeError):
                return self._json(400, {"error": "bad request"})
            folder = self._folder(rel)
            if not folder:
                return self._json(404, {"error": "unknown folder"})
            if route == "/api/delete-video":
                return self._json(200, remove_video(folder))
            return self._json(202, start_download(folder))
        return self._json(404, {"error": "not found"})

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self._api("GET")
        return super().do_GET()

    def do_POST(self):
        return self._api("POST")

    def end_headers(self):
        if "Range" not in self.headers:
            self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


# The video steps live in scripts/video/; shared code never imports them, it runs their CLI.
VIDEO_CLI = Path(__file__).resolve().parent.parent / "video" / "download_video.py"


def video_cli(folder: Path, *args: str) -> tuple[int, object]:
    """Run `video/download_video.py <folder> <args>`; returns (exit code, parsed JSON stdout or the error text)."""
    p = subprocess.run([sys.executable, str(VIDEO_CLI), str(folder), *args], capture_output=True, text=True)
    if p.returncode != 0:
        return p.returncode, (p.stderr.strip().splitlines() or ["failed"])[-1].removeprefix("[tell-me] ")
    return 0, json.loads(p.stdout or "null")


def video_state(folder: Path) -> dict:
    """What the page needs to know about the folder's video."""
    _, status = video_cli(folder, "--status")
    if isinstance(status, dict):
        return {k: status.get(k) for k in ("status", "progress", "stream", "error") if status.get(k) is not None}
    meta = read_json(folder / "metadata.json")
    if meta.get("video_file") and (folder / meta["video_file"]).exists():
        return {"status": "done", "video_file": meta["video_file"], "quality": meta.get("video_quality")}
    return {"status": "none"}


def remove_video(folder: Path) -> dict:
    """Delete the folder's video; download_video.py --delete re-renders the note (the page then offers the download again)."""
    code, out = video_cli(folder, "--delete")
    if code != 0:
        return {"status": "running", "error": out}
    return {"status": "none", "deleted": Path(out["deleted"]).name if out.get("deleted") else None}


def start_download(folder: Path) -> dict:
    """Same download as video/prepare.py's default: best quality, into <folder>/video.<ext>, in the background."""
    state = video_state(folder)
    meta = read_json(folder / "metadata.json")
    if state["status"] == "running" or (state["status"] == "done" and meta.get("video_quality") == "best"):
        return state
    args = [meta["webpage_url"], "--background", "--quality", "best"]
    if meta.get("video_quality"):
        args += ["--have-quality", meta["video_quality"]]
    if os.environ.get("DM_SUMMARIZE_VIDEO_BROWSER"):
        args += ["--cookies-from-browser", os.environ["DM_SUMMARIZE_VIDEO_BROWSER"]]
    video_cli(folder, *args)
    return video_state(folder)


def port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def base_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def ensure_running(root: Path | None = None, port: int = DEFAULT_PORT) -> str:
    """Base URL of a running library server; starts one detached when needed."""
    root = (root or library_root()).resolve()
    state = read_json(root / STATE_FILE)
    if state.get("port") and port_open(state["port"]):
        return base_url(state["port"])
    while port_open(port):  # taken by something else
        port += 1
    logf = open(root / ".server.log", "w")
    proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--port", str(port), "--root", str(root)],
                            stdin=subprocess.DEVNULL, stdout=logf, stderr=logf, start_new_session=True)
    write_json(root / STATE_FILE, {"pid": proc.pid, "port": port})
    for _ in range(50):
        if port_open(port):
            log(f"library server started: {base_url(port)} (pid {proc.pid})")
            return base_url(port)
        time.sleep(0.1)
    raise RuntimeError(f"library server did not start, see {root / '.server.log'}")


def page_url(page: Path, root: Path | None = None) -> str:
    """http URL of a page under the library root (starting the server), else its file:// URI."""
    from library import root_of
    root = root or root_of(page.parent)
    if root is None:
        return page.resolve().as_uri()
    return f"{ensure_running(root)}/{page.resolve().relative_to(root).as_posix()}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--root", type=Path, help="library root (default: $TELL_ME_ROOT or ~/me/summaries)")
    ap.add_argument("--ensure", action="store_true", help="start in the background if needed and print the base URL")
    ap.add_argument("--stop", action="store_true", help="stop the background server")
    args = ap.parse_args(argv)
    root = (args.root or library_root()).resolve()
    if args.ensure:
        print(ensure_running(root, args.port))
        return 0
    if args.stop:
        state = read_json(root / STATE_FILE)
        if state.get("pid"):
            try:
                os.kill(state["pid"], signal.SIGTERM)
            except OSError:
                pass
        (root / STATE_FILE).unlink(missing_ok=True)
        print("stopped")
        return 0
    handler = lambda *a, **kw: RangeHandler(*a, directory=str(root), **kw)  # noqa: E731
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as httpd:
        log(f"serving {root} at {base_url(args.port)}")
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    run_main(main)

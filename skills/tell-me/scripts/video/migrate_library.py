#!/usr/bin/env python3
"""One-off migration of a video library written before the multi-source layout. Dry run by default.

For every video folder under <root>/videos:
  - transcript.md -> content.md
  - metadata.json gains the shared contract fields (source, url, author, published, fetched, site,
    word_count, extractor, content_file, extras), derived from its yt-dlp keys
  - summary.html / digest.html is re-rendered (the sidebar script moved to <root>/library.js)
Then <root>/library.js is rebuilt, the stale <root>/videos/library.js is removed and a library
server still serving the old videos root is stopped. Running it again finds nothing to do.

Usage: migrate_library.py [--root DIR] [--apply]
Folders whose metadata.json can't be read, or whose video is still downloading, are skipped (listed).
Prints one JSON object: {root, apply, folders: [{dir, actions}], skipped: [{dir, skipped}], removed, stopped}.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

from _common import (CONTRACT_KEYS, contract, library_root, log, read_json, run_main, source_root,
                     write_json)

OLD_CONTENT = "transcript.md"
CONTENT = "content.md"


def load(meta_path: Path) -> dict | None:
    """metadata.json as a dict, or None when it exists but can't be read (never overwrite it then)."""
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def plan_folder(folder: Path, meta: dict) -> tuple[list[str], dict]:
    """(actions, new metadata) for one folder; no actions when it is already migrated."""
    actions = []
    if meta.get("kind") == "digest":
        return actions, meta
    if (folder / OLD_CONTENT).exists() and not (folder / CONTENT).exists():
        actions.append(f"rename {OLD_CONTENT} -> {CONTENT}")
    missing = [k for k in CONTRACT_KEYS if k not in meta]
    new = dict(meta)
    if missing:
        c = contract(meta)
        content = folder / CONTENT if (folder / CONTENT).exists() else folder / OLD_CONTENT
        c["content_file"] = CONTENT
        c["word_count"] = len(content.read_text(encoding="utf-8").split()) if content.exists() else 0
        c["extras"] = {"views": meta.get("view_count"), "chapters": len(meta.get("chapters") or [])}
        new |= {k: c[k] for k in missing}
        actions.append(f"add contract fields: {', '.join(missing)}")
    return actions, new


def migrate_folder(folder: Path, root: Path | None = None, apply: bool = True) -> dict | None:
    """Migrate one folder: {dir, actions} or {dir, skipped}; None when there is nothing to do.
    video/prepare.py and download_video.py call this for the folder they touch."""
    root = (root or library_root()).resolve()
    meta_path = folder / "metadata.json"
    meta = load(meta_path)
    if meta is None:
        return {"dir": str(folder), "skipped": "metadata.json can't be read; fix or delete it by hand"}
    actions, new = plan_folder(folder, meta)
    note = folder / ("digest.md" if new.get("kind") == "digest" else "summary.md")
    page = note.with_suffix(".html")
    # Pages rendered before the move load ../../../library.js (the old videos root).
    if page.exists() and 'library.js"' in (text := page.read_text(encoding="utf-8")) \
            and f'src="{os.path.relpath(root, folder.resolve()).replace(os.sep, "/")}/library.js"' not in text:
        actions.append("re-render page")
    if not actions:
        return None
    if (read_json(folder / ".video-download.json")).get("status") == "running":
        return {"dir": str(folder), "skipped": "a video download is running; run the migration again when it is done"}
    if apply:
        if (folder / OLD_CONTENT).exists() and not (folder / CONTENT).exists():
            (folder / OLD_CONTENT).rename(folder / CONTENT)
        if new != meta:
            # re-read right before writing: merge, so nothing written meanwhile is lost
            write_json(meta_path, (load(meta_path) or meta) | {k: v for k, v in new.items() if k not in meta})
        if note.exists():
            from render_html import write
            write(folder, index=False)
    return {"dir": str(folder), "actions": actions}


def serves(pid: int, videos: Path) -> bool:
    """True when pid is a serve_library.py serving exactly this videos folder (a copied .server.json
    must not stop someone else's server)."""
    p = subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True)
    cmd = p.stdout.strip()
    return "serve_library.py" in cmd and f"--root {videos.resolve()}" in cmd


def stop_old_server(videos: Path) -> int | None:
    """Stop a library server that was started with the old videos-only root; returns its pid."""
    state = read_json(videos / ".server.json")
    (videos / ".server.json").unlink(missing_ok=True)
    pid = state.get("pid")
    if not pid or not serves(pid, videos):
        return None
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return None
    return pid


def migrate(root: Path, apply: bool) -> dict:
    videos = source_root("video", root)
    folders, skipped = [], []
    for meta_path in sorted(videos.rglob("metadata.json")) if videos.is_dir() else []:
        result = migrate_folder(meta_path.parent, root, apply)
        if result:
            (skipped if "skipped" in result else folders).append(result)
    stale = videos / "library.js"
    removed = str(stale) if stale.exists() else None
    stopped = None
    if apply:
        if stale.exists():
            stale.unlink()
        stopped = stop_old_server(videos)
        if folders or removed:
            from library import write_index
            write_index(root)
    return {"root": str(root), "apply": apply, "folders": folders, "skipped": skipped, "removed": removed,
            "stopped": stopped}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, help="library root (default: $TELL_ME_ROOT or ~/me/summaries)")
    ap.add_argument("--apply", action="store_true", help="make the changes (default: only print them)")
    args = ap.parse_args(argv)
    if args.root:
        os.environ["TELL_ME_ROOT"] = str(args.root)
    root = library_root().resolve()
    result = migrate(root, args.apply)
    n = len(result["folders"])
    log(f"{n} folder(s) {'migrated' if args.apply else 'to migrate (dry run, pass --apply)'}" if n or result["removed"]
        else "nothing to migrate")
    for s in result["skipped"]:
        log(f"skipped {s['dir']}: {s['skipped']}")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    run_main(main)

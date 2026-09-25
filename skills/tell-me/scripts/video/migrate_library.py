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
Prints one JSON object: {root, apply, folders: [{dir, actions}], removed, stopped}.
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


def plan_folder(folder: Path) -> tuple[list[str], dict]:
    """(actions, new metadata) for one folder; no actions when it is already migrated."""
    meta = read_json(folder / "metadata.json")
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
    folders = []
    for meta_path in sorted(videos.rglob("metadata.json")) if videos.is_dir() else []:
        folder = meta_path.parent
        actions, new = plan_folder(folder)
        note = folder / ("digest.md" if new.get("kind") == "digest" else "summary.md")
        page = note.with_suffix(".html")
        # Pages rendered before the move load ../../../library.js (the old videos root).
        if page.exists() and 'library.js"' in (text := page.read_text(encoding="utf-8")) \
                and f'src="{os.path.relpath(root, folder.resolve()).replace(os.sep, "/")}/library.js"' not in text:
            actions.append("re-render page")
        if not actions:
            continue
        folders.append({"dir": str(folder), "actions": actions})
        if not apply:
            continue
        if (folder / OLD_CONTENT).exists() and not (folder / CONTENT).exists():
            (folder / OLD_CONTENT).rename(folder / CONTENT)
        if new != read_json(meta_path):
            write_json(meta_path, new)
        if note.exists():
            from render_html import write
            write(folder, index=False)
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
    return {"root": str(root), "apply": apply, "folders": folders, "removed": removed, "stopped": stopped}


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
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    run_main(main)

#!/usr/bin/env python3
"""Extract scene-change keyframes from a prepared video folder, for the agent to look at.

Uses ffmpeg scene detection (`select='eq(n,0)+gt(scene,T)'` + showinfo for timestamps),
keeps at most --max frames (even subsampling), and falls back to fixed intervals when a
video has too few scene changes (e.g. static slides). Writes <dir>/frames/NNN.jpg and
<dir>/frames/index.md (frame -> timestamp link).

Usage: extract_frames.py <video-dir> [--max 40] [--threshold 0.3] [--min 4]
Requires: ffmpeg. The folder must contain video.<ext> (prepare.py downloads it unless --skip-download).
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

import sys

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

from _common import SkillError, find_file, fmt_ts, log, probe_duration, read_json, require, run_main, ts_link

_PTS_RE = re.compile(r"\bpts_time:\s*([0-9.]+)")


def parse_showinfo(stderr: str) -> list[float]:
    """Frame timestamps from ffmpeg showinfo output, in output order."""
    return [float(m.group(1)) for line in stderr.splitlines() if "Parsed_showinfo" in line
            for m in [_PTS_RE.search(line)] if m]


def sample_indices(n: int, max_n: int) -> list[int]:
    """Evenly spread max_n of n indices, always keeping the first and last."""
    if n <= max_n:
        return list(range(n))
    if max_n <= 1:
        return [0]
    return sorted({round(i * (n - 1) / (max_n - 1)) for i in range(max_n)})


def min_scene_frames(duration: float, floor: int) -> int:
    """Scene frames needed before trusting scene detection: ~1 per 30s, between 2 and `floor`."""
    return min(floor, max(2, int(duration // 30)))


def interval_seconds(duration: float, count: int) -> float:
    return max(duration / max(count, 1), 1.0)


def render_index(info: dict, frames: list[tuple[str, float]], method: str) -> str:
    rows = [f"# Frames: {info.get('title', '')}", "", f"method: {method}, count: {len(frames)}", "",
            "| # | time | file |", "|---|------|------|"]
    rows += [f"| {i + 1} | {ts_link(info, t)} | ![{fmt_ts(t)}]({name}) |" for i, (name, t) in enumerate(frames)]
    return "\n".join(rows) + "\n"


def _ffmpeg(video: Path, vf: str, pattern: Path) -> subprocess.CompletedProcess:
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-i", str(video), "-vf", vf,
           "-vsync", "vfr", "-q:v", "3", str(pattern)]
    return subprocess.run(cmd, capture_output=True, text=True)


def extract(folder: Path, max_frames: int = 40, threshold: float = 0.3, min_frames: int = 4) -> Path:
    require("ffmpeg")
    video = find_file(folder, "video")
    if not video:
        raise SkillError(f"no video.<ext> in {folder}; run prepare.py without --skip-download first")
    info = read_json(folder / "metadata.json")
    duration = float(info.get("duration") or 0) or probe_duration(video) or 60.0
    out = folder / "frames"
    tmp = folder / "frames.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    scale = "scale='min(1280,iw)':-2"

    log(f"detecting scene changes (threshold {threshold})")
    p = _ffmpeg(video, f"select='eq(n,0)+gt(scene,{threshold})',showinfo,{scale}", tmp / "%05d.jpg")
    files = sorted(tmp.glob("*.jpg"))
    times = parse_showinfo(p.stderr)
    method = f"scene>{threshold}"
    if len(files) < min_scene_frames(duration, min_frames):
        step = interval_seconds(duration, max_frames)
        log(f"only {len(files)} scene frames; sampling every {step:.0f}s instead")
        shutil.rmtree(tmp)
        tmp.mkdir()
        p = _ffmpeg(video, f"fps=1/{step:.3f},showinfo,{scale}", tmp / "%05d.jpg")
        files = sorted(tmp.glob("*.jpg"))
        times = [i * step for i in range(len(files))]
        method = f"interval {step:.0f}s"
    if p.returncode != 0 and not files:
        shutil.rmtree(tmp, ignore_errors=True)
        raise SkillError(f"ffmpeg failed:\n{p.stderr.strip()[-800:]}")
    times = (times + [0.0] * len(files))[: len(files)]

    shutil.rmtree(out, ignore_errors=True)
    out.mkdir()
    kept = []
    for n, idx in enumerate(sample_indices(len(files), max_frames), start=1):
        name = f"{n:03d}.jpg"
        files[idx].rename(out / name)
        kept.append((name, times[idx]))
    shutil.rmtree(tmp, ignore_errors=True)
    index = out / "index.md"
    index.write_text(render_index(info, kept, method), encoding="utf-8")
    log(f"frames: {len(kept)} ({method}) -> {out}")
    return index


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dir", type=Path)
    ap.add_argument("--max", type=int, default=40, help="maximum frames to keep (default 40)")
    ap.add_argument("--threshold", type=float, default=0.3, help="ffmpeg scene threshold 0-1 (default 0.3)")
    ap.add_argument("--min", type=int, default=4, help="upper bound for the scene-frame minimum (~1 per 30s) before falling back to intervals")
    args = ap.parse_args(argv)
    print(extract(args.dir, args.max, args.threshold, args.min))
    return 0


if __name__ == "__main__":
    run_main(main)

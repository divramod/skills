#!/usr/bin/env python3
"""Find and delete the build artifacts of a git worktree.

Usage: cleanup.py <command> [options]
  list [--deps] [--json]   the artifacts of this worktree with kind and size; ignored paths that are not known as
                           artifacts are listed as `unknown` (never deleted by `delete --kinds`)
  busy                     processes whose command line names this worktree (a build still running); exit 1 if any
  delete [--deps] [--dry-run] [PATH...]
                           delete PATHs (worktree-relative), or with none every `build` and `generated` artifact
                           (+ `deps` with --deps). Every path must be git-ignored, hold no tracked file and not be
                           protected.

Artifacts are git-ignored, untracked paths that match locations.tsv (known hal project locations) or a generic
pattern (target/, build/, .build/, dist/, node_modules/, __pycache__/, ...). Protected, never deleted: .git, .hal,
.secrets, .env*, plans/, shotfiles/, *.machine.toml. Exit 2: git is missing.
"""
import fnmatch
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Directory names that are artifacts wherever they are ignored.
GENERIC = {
    "build": ["target", "build", ".build", "dist", "out", ".next", ".nuxt", ".turbo", ".parcel-cache",
              ".svelte-kit", "coverage", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
              ".gradle", ".swiftpm", "DerivedData", ".cache", "*.egg-info", "*.xcresult", "*.noindex", ".tox"],
    "deps": ["node_modules", ".venv", "venv", "Pods", "Carthage", "vendor/bundle"],
}
PROTECTED = [".git", ".hal", ".hal/*", ".secrets", ".secrets/*", ".env", ".env.*", "plans", "plans/*",
             "shotfiles", "shotfiles/*", "*.machine.toml", "*/.env", "*/.env.*"]


def git(*args, check=True):
    if not shutil.which("git"):
        print("cleanup.py: git is missing; run install-prerequisites.sh", file=sys.stderr)
        sys.exit(2)
    return subprocess.run(["git", *args], capture_output=True, text=True, check=check).stdout


def toplevel() -> Path:
    try:
        return Path(git("rev-parse", "--show-toplevel").strip())
    except subprocess.CalledProcessError:
        print("cleanup.py: not inside a git worktree", file=sys.stderr)
        sys.exit(1)


def known():
    rows = []
    for line in (HERE / "locations.tsv").read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            path, kind, how = (line.split("\t") + ["", ""])[:3]
            rows.append((path.strip(), kind.strip(), how.strip()))
    return rows


def classify(rel: str):
    """(kind, how) for an ignored path, or ('unknown', ''). A path inside a known location has its kind."""
    parts = rel.split("/")
    prefixes = ["/".join(parts[:i]) for i in range(len(parts), 0, -1)]
    for prefix in prefixes:
        for pattern, kind, how in known():
            if fnmatch.fnmatch(prefix, pattern) or fnmatch.fnmatch(prefix, pattern.replace("**/", "")):
                return kind, how
    for prefix in prefixes:
        name = prefix.rsplit("/", 1)[-1]
        for kind, names in GENERIC.items():
            if any(fnmatch.fnmatch(name, n) or prefix.endswith("/" + n) or prefix == n for n in names):
                return kind, ""
    return "unknown", ""


def protected(rel: str) -> bool:
    return any(fnmatch.fnmatch(rel, p) for p in PROTECTED)


def size(path: Path) -> int:
    if path.is_symlink() or path.is_file():
        return path.lstat().st_size
    total = 0
    for dirpath, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.lstat(os.path.join(dirpath, f)).st_size
            except OSError:
                pass
    return total


def human(n: int) -> str:
    for unit in ("B", "K", "M", "G", "T"):
        if n < 1024 or unit == "T":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024


def ignored(top: Path):
    """Git-ignored untracked entries, collapsed to the outermost ignored directory."""
    out = git("-C", str(top), "ls-files", "--others", "--ignored", "--exclude-standard", "--directory")
    return sorted({line.rstrip("/") for line in out.splitlines() if line.strip()})


def artifacts(top: Path, deps: bool):
    entries = [e for e in ignored(top) if not protected(e)]
    kinds = {e: classify(e) for e in entries}
    # git lists some ignored files and their untracked directory both: an unknown directory with listed content
    # gives way to that content, a known one covers it.
    keep = [e for e in entries
            if not (kinds[e][0] == "unknown" and any(o.startswith(e + "/") for o in entries))]
    keep = [e for e in keep if not any(e.startswith(o + "/") for o in keep)]
    rows = []
    for rel in keep:
        kind, how = kinds[rel]
        path = top / rel
        if not path.exists() and not path.is_symlink():
            continue
        rows.append({"path": rel, "kind": kind, "size": size(path), "rebuild": how,
                     "selected": kind in ("build", "generated") or (deps and kind == "deps")})
    return rows


def cmd_list(args):
    top = toplevel()
    rows = artifacts(top, "--deps" in args)
    if "--json" in args:
        print(json.dumps({"worktree": str(top), "artifacts": rows}, indent=2))
        return 0
    print(f"worktree {top}")
    for r in sorted(rows, key=lambda r: -r["size"]):
        mark = "*" if r["selected"] else " "
        print(f"{mark} {human(r['size']):>7}  {r['kind']:<9}  {r['path']}" + (f"  ({r['rebuild']})" if r["rebuild"] else ""))
    sel = sum(r["size"] for r in rows if r["selected"])
    print(f"selected (*): {human(sel)} of {human(sum(r['size'] for r in rows))}")
    return 0


def cmd_busy(_args):
    top = str(toplevel())
    out = subprocess.run(["ps", "-A", "-o", "pid=,command="], capture_output=True, text=True).stdout
    me = {os.getpid(), os.getppid()}
    hits = []
    for line in out.splitlines():
        pid, _, cmd = line.strip().partition(" ")
        if top + "/" in cmd + "/" and int(pid) not in me and "cleanup.py" not in cmd:
            hits.append(f"{pid}\t{cmd}")
    print("\n".join(hits) if hits else "idle")
    return 1 if hits else 0


def check(top: Path, rel: str):
    """Why rel must not be deleted, or None."""
    path = (top / rel).resolve() if not (top / rel).is_symlink() else (top / rel).parent.resolve() / (top / rel).name
    if top.resolve() not in path.parents:
        return "outside the worktree"
    rel = str(path.relative_to(top.resolve()))
    if protected(rel):
        return "protected"
    if not (top / rel).exists() and not (top / rel).is_symlink():
        return "does not exist"
    if git("-C", str(top), "ls-files", "--", rel).strip():
        return "holds tracked files"
    if subprocess.run(["git", "-C", str(top), "check-ignore", "-q", rel]).returncode != 0:
        return "not git-ignored"
    return None


def cmd_delete(args):
    top = toplevel()
    dry = "--dry-run" in args
    paths = [a for a in args if not a.startswith("--")]
    if not paths:
        paths = [r["path"] for r in artifacts(top, "--deps" in args) if r["selected"]]
    status, freed = 0, 0
    for rel in paths:
        why = check(top, rel.rstrip("/"))
        if why:
            print(f"skip    {rel}: {why}")
            status = 1
            continue
        path = top / rel.rstrip("/")
        n = size(path)
        if not dry:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
        freed += n
        print(f"{'would delete' if dry else 'deleted'} {human(n):>7}  {rel}")
    print(f"{'would free' if dry else 'freed'} {human(freed)}")
    return status


COMMANDS = {"list": cmd_list, "busy": cmd_busy, "delete": cmd_delete}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__.strip(), file=sys.stderr)
        sys.exit(1)
    sys.exit(COMMANDS[sys.argv[1]](sys.argv[2:]))

#!/usr/bin/env python3
"""The deterministic half of `/mtm config`: a repo's merge-to-main hooks.

    hooks.py apps  [--repo DIR]             the repo's apps and libs, their stack, the parts covering them (JSON)
    hooks.py init  [--repo DIR] [--force]   install or update the managed dispatcher (phase files + lib.sh)
    hooks.py check [--repo DIR]             lint the hooks: syntax, paths files, pathspecs, coverage (JSON)
    hooks.py try <phase> [--repo DIR] [--part P[,Q]] [--all-changed] [--yes] [--keep]
                                            run a phase like a landing would; main-* in a throwaway worktree

The layout (references/hooks.md): `.hal/hooks/merge-to-main/<phase>.sh` call `lib.sh`, which runs
`parts/<part>/<phase>.sh` for every part; `parts/<part>/paths` lists the part's files as git pathspecs.
Exit codes: 0 ok, 1 failed (check errors, init conflicts, the hook's own failure), 2 missing tool.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PHASES = ("worktree-pre-merge", "main-pre-commit", "main-post-commit")
MANAGED = "managed by /mtm config"
TEMPLATES = Path(__file__).resolve().parent.parent / "templates" / "hooks" / "merge-to-main"
HOOKS = Path(".hal/hooks/merge-to-main")
PART_FILES = {"paths", "README.md", *(f"{p}.sh" for p in PHASES)}

# Marker file (or dir, trailing "/") in an app dir -> stack name.
STACK_MARKERS = [
    ("Cargo.toml", "cargo"),
    ("package.json", "node"),
    ("bun.lock", "bun"),
    ("bun.lockb", "bun"),
    ("package-lock.json", "npm"),
    ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("Package.swift", "swiftpm"),
    ("project.yml", "xcodegen"),
    ("build.sh", "build.sh"),
    ("go.mod", "go"),
    ("pyproject.toml", "python"),
    ("Makefile", "make"),
    ("justfile", "just"),
    ("lua/", "lua"),
    ("plugin/", "vim-plugin"),
    ("tests/minimal_init.lua", "plenary"),
]


def require(tool: str) -> None:
    if shutil.which(tool) is None:
        hint = {"git": "brew install git", "bash": "brew install bash"}.get(tool, f"install {tool}")
        print(f"hooks.py: missing {tool} -> {hint}; or run scripts/install-prerequisites.sh", file=sys.stderr)
        sys.exit(2)


def git(args: list[str], cwd: Path, check: bool = True) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and done.returncode != 0:
        raise SystemExit(f"hooks.py: git {' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout.strip()


def repo_root(repo: str | None) -> Path:
    start = Path(repo or ".").resolve()
    root = git(["rev-parse", "--show-toplevel"], start, check=False)
    if not root:
        raise SystemExit(f"hooks.py: {start} is not in a git repository")
    return Path(root)


def main_root(root: Path) -> Path:
    common = Path(git(["rev-parse", "--path-format=absolute", "--git-common-dir"], root))
    return common.parent if common.name == ".git" else root


def default_branch(root: Path) -> str:
    head = git(["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"], root, check=False)
    if head.startswith("origin/"):
        return head.removeprefix("origin/")
    for name in ("main", "master"):
        if git(["rev-parse", "--verify", "--quiet", f"refs/heads/{name}"], root, check=False):
            return name
    return "main"


def default_ref(root: Path, branch: str) -> str:
    ok = git(["rev-parse", "--verify", "--quiet", f"origin/{branch}^{{commit}}"], root, check=False)
    return f"origin/{branch}" if ok else branch


def read_paths(file: Path) -> list[str]:
    if not file.is_file():
        return []
    specs = []
    for line in file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            specs.append(line)
    return specs


def positive(spec: str) -> str | None:
    """The include form of an exclude pathspec, None for an include."""
    if spec.startswith((":!", ":^")):
        return spec[2:]
    if spec.startswith(":(") and ")" in spec:
        magic, rest = spec[2:].split(")", 1)
        words = [w for w in magic.split(",") if w]
        if "exclude" in words:
            words.remove("exclude")
            return f":({','.join(words)}){rest}" if words else rest
    return None


def ls_files(root: Path, specs: list[str]) -> set[str]:
    out = subprocess.run(["git", "ls-files", "-z", "--", *specs], cwd=root, capture_output=True, text=True)
    return {f for f in out.stdout.split("\0") if f}


def tracked(root: Path, specs: list[str]) -> set[str]:
    """The tracked files the pathspecs select, as `git diff -- <specs>` would. Excludes are applied here:
    `git ls-files -- ':(glob)a/**' ':(exclude,glob)**/*.md'` selects nothing (git 2.54)."""
    excludes = [p for p in map(positive, specs) if p is not None]
    includes = [s for s in specs if positive(s) is None]
    if not includes:
        return set()
    files = ls_files(root, includes)
    return files - ls_files(root, excludes) if excludes and files else files


def parts(root: Path) -> list[dict]:
    result = []
    base = root / HOOKS / "parts"
    for d in sorted(p for p in base.glob("*") if p.is_dir()):
        specs = read_paths(d / "paths")
        result.append({
            "name": d.name,
            "phases": [p for p in PHASES if (d / f"{p}.sh").is_file()],
            "paths": specs,
            "files": sorted(tracked(root, specs)),
        })
    return result


def stack(root: Path, rel: str) -> dict:
    d = root / rel
    found = []
    for marker, name in STACK_MARKERS:
        hit = (d / marker.rstrip("/")).is_dir() if marker.endswith("/") else (d / marker).is_file()
        if hit and name not in found:
            found.append(name)
    info: dict = {"stack": found}
    pkg = d / "package.json"
    if pkg.is_file():
        try:
            info["scripts"] = sorted(json.loads(pkg.read_text()).get("scripts", {}))
        except json.JSONDecodeError:
            info["scripts"] = []
    if "cargo" in found:
        for up in [d, *d.parents]:
            toml = up / "Cargo.toml"
            if toml.is_file() and "[workspace]" in toml.read_text():
                info["workspace"] = os.path.relpath(up, root)
                break
            if up == root:
                break
    return info


def units(root: Path) -> list[dict]:
    """code/<language>/{apps,libs}/<name>, or the repo itself when it has no such folders."""
    found = []
    for kind in ("apps", "libs"):
        for d in sorted(root.glob(f"code/*/{kind}/*")):
            if d.is_dir():
                found.append({"name": d.name, "kind": kind[:-1], "language": d.parent.parent.name,
                              "path": str(d.relative_to(root))})
    if not any(u["kind"] == "app" for u in found):
        found.insert(0, {"name": root.name, "kind": "app", "language": None, "path": "."})
    return found


def cmd_apps(root: Path) -> int:
    ps = parts(root)
    out = []
    for u in units(root):
        prefix = "" if u["path"] == "." else u["path"] + "/"
        u["parts"] = [p["name"] for p in ps if any(f.startswith(prefix) for f in p["files"])]
        u.update(stack(root, u["path"]))
        out.append(u)
    hooks = root / HOOKS
    print(json.dumps({
        "root": str(root),
        "hooks_dir": str(HOOKS),
        "managed": all(MANAGED in (hooks / f"{p}.sh").read_text() for p in PHASES
                       if (hooks / f"{p}.sh").is_file()) and (hooks / "lib.sh").is_file(),
        "parts": [{k: p[k] for k in ("name", "phases", "paths")} for p in ps],
        "units": out,
    }, indent=2))
    return 0


def cmd_init(root: Path, force: bool) -> int:
    hooks = root / HOOKS
    hooks.mkdir(parents=True, exist_ok=True)
    (hooks / "parts").mkdir(exist_ok=True)
    report, conflicts = {}, []
    for tpl in sorted(TEMPLATES.iterdir()):
        target = hooks / tpl.name
        new = tpl.read_text()
        if not target.exists():
            state = "created"
        elif target.read_text() == new:
            report[tpl.name] = "unchanged"
            continue
        elif MANAGED in target.read_text():
            state = "updated"
        elif force:
            state = "replaced"
        else:
            report[tpl.name] = "conflict: not managed; move it into parts/<part>/, then init --force"
            conflicts.append(tpl.name)
            continue
        target.write_text(new)
        report[tpl.name] = state
    print(json.dumps({"hooks_dir": str(HOOKS), "files": report}, indent=2))
    return 1 if conflicts else 0


def cmd_check(root: Path) -> int:
    hooks = root / HOOKS
    errors, warnings = [], []
    for phase in PHASES:
        f = hooks / f"{phase}.sh"
        if f.is_file() and MANAGED not in f.read_text():
            warnings.append(f"{phase}.sh is not managed: parts/*/{phase}.sh do not run (hooks.py init)")
        elif f.is_file() and f.read_text() != (TEMPLATES / f.name).read_text():
            warnings.append(f"{phase}.sh differs from the template (hooks.py init updates it)")
    lib = hooks / "lib.sh"
    if lib.is_file() and lib.read_text() != (TEMPLATES / "lib.sh").read_text():
        warnings.append("lib.sh differs from the template (hooks.py init updates it)")
    if any(MANAGED in (hooks / f"{p}.sh").read_text() for p in PHASES if (hooks / f"{p}.sh").is_file()) \
            and not lib.is_file():
        errors.append("lib.sh is missing (hooks.py init)")
    for script in sorted(hooks.rglob("*.sh")) if hooks.is_dir() else []:
        done = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        if done.returncode != 0:
            errors.append(f"{script.relative_to(root)}: {done.stderr.strip()}")
    ps = parts(root)
    for p in ps:
        d = hooks / "parts" / p["name"]
        if not p["phases"]:
            warnings.append(f"parts/{p['name']}: no phase script, it never runs")
        for extra in sorted(f.name for f in d.iterdir() if f.name not in PART_FILES):
            warnings.append(f"parts/{p['name']}/{extra}: not a phase script ({', '.join(PHASES)}), never run")
        if not p["paths"]:
            errors.append(f"parts/{p['name']}/paths: missing or lists no pathspec")
            continue
        for spec in p["paths"]:
            if spec.startswith(":(exclude") or spec.startswith(":!") or spec.startswith(":^"):
                continue
            if not tracked(root, [spec]):
                errors.append(f"parts/{p['name']}/paths: `{spec}` matches no tracked file")
    for u in units(root):
        prefix = "" if u["path"] == "." else u["path"] + "/"
        if u["kind"] == "app" and not any(any(f.startswith(prefix) for f in p["files"]) for p in ps):
            warnings.append(f"app {u['path']} is in no part's paths")
    print(json.dumps({"ok": not errors, "errors": errors, "warnings": warnings}, indent=2))
    return 0 if not errors else 1


def run_hook(phase: str, cwd: Path, env: dict) -> int:
    script = cwd / HOOKS / f"{phase}.sh"
    if not script.is_file():
        print(f"hooks.py: {HOOKS / (phase + '.sh')} does not exist", file=sys.stderr)
        return 1
    print(f"hooks.py: running {phase}.sh in {cwd}", file=sys.stderr, flush=True)
    return subprocess.run(["bash", str(script)], cwd=cwd, env={**os.environ, **env}).returncode


def cmd_try(root: Path, phase: str, part: str | None, all_changed: bool, yes: bool, keep: bool) -> int:
    if phase == "main-post-commit" and not yes:
        print("hooks.py: main-post-commit does what a landing does after the merge (installs, restarts); "
              "rerun with --yes once the user agreed", file=sys.stderr)
        return 1
    branch = default_branch(root)
    env = {
        "HAL_HOOK_WORKTREE": str(root),
        "HAL_HOOK_BRANCH": git(["rev-parse", "--abbrev-ref", "HEAD"], root),
        "HAL_HOOK_MAIN_ROOT": str(main_root(root)),
        "HAL_HOOK_DEFAULT_BRANCH": branch,
    }
    if part:
        env["HAL_HOOK_ONLY_PART"] = part
    if all_changed:
        env["HAL_HOOK_FORCE_CHANGED"] = "1"
    if phase == "worktree-pre-merge":
        return run_hook(phase, root, env)

    # main-*: the default branch with this branch merged in, in a throwaway worktree; the working tree's hooks
    # are copied over it, so uncommitted hook edits are tried too.
    tmp = Path(tempfile.mkdtemp(prefix="mtm-try-")) / root.name
    head = git(["rev-parse", "HEAD"], root)
    git(["worktree", "add", "--quiet", "--detach", str(tmp), default_ref(root, branch)], root)
    try:
        merged = subprocess.run(["git", "merge", "--quiet", "--no-ff", "--no-commit", head],
                                cwd=tmp, capture_output=True, text=True)
        if merged.returncode != 0:
            print(f"hooks.py: merging this branch into {branch} conflicts; run /mfm first\n{merged.stdout}",
                  file=sys.stderr)
            return 1
        if phase == "main-post-commit":
            git(["commit", "--quiet", "--no-verify", "--allow-empty", "-m", "hooks.py try"], tmp)
        shutil.rmtree(tmp / HOOKS, ignore_errors=True)
        if (root / HOOKS).is_dir():
            shutil.copytree(root / HOOKS, tmp / HOOKS)
        env["HAL_HOOK_MAIN_ROOT"] = str(tmp)
        return run_hook(phase, tmp, env)
    finally:
        if keep:
            print(f"hooks.py: kept {tmp}; remove with: git worktree remove --force {tmp}", file=sys.stderr)
        else:
            git(["worktree", "remove", "--force", str(tmp)], root, check=False)
            shutil.rmtree(tmp.parent, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="hooks.py", description="The merge-to-main hooks of a repo (/mtm config).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("apps", "init", "check", "try"):
        p = sub.add_parser(name)
        p.add_argument("--repo")
        if name == "init":
            p.add_argument("--force", action="store_true", help="replace unmanaged phase files")
        if name == "try":
            p.add_argument("phase", choices=PHASES)
            p.add_argument("--part", help="only these parts (comma separated)")
            p.add_argument("--all-changed", action="store_true", help="count every part as changed")
            p.add_argument("--yes", action="store_true", help="needed for main-post-commit (real side effects)")
            p.add_argument("--keep", action="store_true", help="keep the throwaway worktree")
    args = ap.parse_args(argv)
    for tool in ("git", "bash"):
        require(tool)
    root = repo_root(args.repo)
    if args.cmd == "apps":
        return cmd_apps(root)
    if args.cmd == "init":
        return cmd_init(root, args.force)
    if args.cmd == "check":
        return cmd_check(root)
    return cmd_try(root, args.phase, args.part, args.all_changed, args.yes, args.keep)


if __name__ == "__main__":
    sys.exit(main())

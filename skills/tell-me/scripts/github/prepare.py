#!/usr/bin/env python3
"""Prepare a GitHub repo, issue, pull request or discussion for summarizing.

Repo (`github.com/<o>/<r>`, also `/tree/<ref>/<path>` and `/blob/<ref>/<path>`, which read that ref and put
that path first: a file of any kind, or the markdown in a folder):
1. The API (client.py: gh, else REST) gives the repo facts, languages, latest release and the commit of the
   default branch (or of the link's ref: a branch, tag or commit, `feature/x` too); the tree lists every path.
2. content.md: a header (description, stars, license, languages, release, last push, topics), the README, the
   file tree (the first 200 paths, shallow first) and the docs: markdown at the root (ARCHITECTURE.md, ...) and
   under docs/ (focus path first), up to a size budget. Every text block gets an [L<n>] link to that line at
   the commit (anchors.py), headings a [#] link.
3. --deep packs the whole repository at that same commit with repomix (`npx repomix --remote --remote-branch
   <sha> --compress`, tests, fixtures and lock files left out) into repo-pack.md next to it. A refetch without
   --deep drops a pack of an older commit.
Issue / pull request / discussion: thread.py (body + comments in discussion shape).
Folder: <root>/repos/github/<owner>/<repo>/ (threads under issues/, pulls/, discussions/). An item prepared
before is reused (--refresh refetches). Prints the source envelope on stdout.

Usage: prepare.py <github url> [--deep] [--refresh]
Requires: nothing (gh recommended: 5000 requests/hour, needed for discussions); npx for --deep.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

from _common import (SkillError, envelope, find_by_id, log, read_json, require, run_main, unique_dir,
                     update_json)
from anchors import anchor_file
from client import GitHub, NotFound
from route import route

REPOMIX = "repomix@1.18.1"
TREE_PATHS = 200
DOC_BUDGET = 120_000  # characters of docs besides the README
DOC_MAX = 40_000  # characters of one doc file
DOC_TRIES = 40  # doc files fetched at most (a docs-heavy repo has thousands)
DOC_FAILS = 3  # consecutive failed fetches that end the docs (a private repo read without access, ...)
README_MAX = 150_000
DEEP_TIMEOUT = 900
BIG_REPO_KB = 200_000  # warn before packing a repo larger than this
LANGS = {"py": "python", "js": "javascript", "mjs": "javascript", "ts": "typescript", "tsx": "tsx", "jsx": "jsx",
         "rs": "rust", "go": "go", "rb": "ruby", "java": "java", "kt": "kotlin", "swift": "swift", "c": "c",
         "h": "c", "cc": "cpp", "cpp": "cpp", "hpp": "cpp", "cs": "csharp", "php": "php", "sh": "bash",
         "bash": "bash", "zsh": "bash", "lua": "lua", "json": "json", "yml": "yaml", "yaml": "yaml",
         "toml": "toml", "html": "html", "css": "css", "scss": "scss", "sql": "sql", "txt": ""}
BIG_PACK_WORDS = 150_000  # warn: more than an agent reads in one go
# test data, fixtures, snapshots and lock files: large, and rarely how the code works
PACK_IGNORE = ",".join(("**/test/**", "**/tests/**", "**/__tests__/**", "**/spec/**", "**/fixtures/**",
                        "**/testdata/**", "**/__snapshots__/**", "**/*.snap", "**/*.lock", "**/package-lock.json",
                        "**/pnpm-lock.yaml", "**/*.min.js", "**/*.svg"))
DOC_DIRS = ("docs/", "doc/", "documentation/", "guide/", "guides/", "wiki/")
SKIP_DIRS = re.compile(r"(^|/)(tests?|__tests__|spec|fixtures?|testdata|examples?|node_modules|vendor|third_party|"
                       r"\.github|dist|build)/", re.I)
MARKDOWN_EXT = (".md", ".mdx", ".markdown", ".rst")
INDEX_NAMES = ("index", "readme", "introduction", "overview", "getting-started")
SKIP_ROOT_DOCS = re.compile(r"^(CHANGELOG|CHANGES|HISTORY|CODE_OF_CONDUCT|LICENSE|SECURITY|SUPPORT|"
                            r"PULL_REQUEST_TEMPLATE|ISSUE_TEMPLATE)\b", re.I)


# ---------------------------------------------------------------- repo facts


def repo_facts(gh: GitHub, repo: str, ref_path: str | None = None) -> dict:
    """The repo's facts and the commit it is read at: the default branch's, or that of the ref that starts
    `ref_path` (a /tree or /blob link's `<ref>/<path>`); `path` is the rest."""
    info = gh.get(f"repos/{repo}")
    repo = info.get("full_name") or repo  # the rest by GitHub's spelling (a renamed repo redirects only here)
    languages = gh.get(f"repos/{repo}/languages") or {}
    try:
        release = gh.get(f"repos/{repo}/releases/latest")
    except NotFound:
        release = None
    ref, path = resolve_ref(gh, repo, ref_path) if ref_path else (info["default_branch"], None)
    try:
        commit = gh.get(f"repos/{repo}/commits/{urllib.parse.quote(ref)}")
    except NotFound:
        raise SkillError(f"{repo} has no branch, tag or commit {ref!r}")
    return {"info": info, "languages": languages, "release": release, "sha": commit["sha"], "ref": ref,
            "path": path, "commit_date": (commit.get("commit") or {}).get("committer", {}).get("date")
            or commit.get("date")}


def resolve_ref(gh: GitHub, repo: str, ref_path: str) -> tuple[str, str | None]:
    """(ref, path) of a /tree or /blob link's `<ref>/<path>`: a ref may hold slashes (`feature/x`), so the
    longest branch or tag that is a whole-segment prefix wins; else the first segment (a commit sha, or a
    branch the listing missed)."""
    segs = [s for s in ref_path.split("/") if s]
    if len(segs) > 1:
        names: set[str] = set()
        for kind in ("heads", "tags"):
            try:
                refs = gh.get(f"repos/{repo}/git/matching-refs/{kind}/{urllib.parse.quote(segs[0])}") or []
            except NotFound:
                refs = []
            names |= {r["ref"].split("/", 2)[2] for r in refs if r.get("ref", "").count("/") >= 2}
        for k in range(len(segs), 0, -1):
            if "/".join(segs[:k]) in names:
                return "/".join(segs[:k]), "/".join(segs[k:]) or None
    return segs[0], "/".join(segs[1:]) or None


def language_share(languages: dict) -> list[str]:
    total = sum(languages.values()) or 1
    return [f"{name} {100 * n / total:.0f}%" for name, n in sorted(languages.items(), key=lambda kv: -kv[1])[:5]
            if 100 * n / total >= 1]


def tree_paths(gh: GitHub, repo: str, sha: str) -> tuple[list[str], bool]:
    """(every file path, whether GitHub cut the listing short)."""
    tree = gh.get(f"repos/{repo}/git/trees/{sha}?recursive=1")
    return [t["path"] for t in tree.get("tree", []) if t.get("type") == "blob"], bool(tree.get("truncated"))


def shown_tree(paths: list[str], limit: int = TREE_PATHS) -> tuple[list[str], int]:
    """The first `limit` paths, shallow ones first (the layout reads better than a deep corner of it)."""
    ranked = sorted(paths, key=lambda p: (p.count("/"), p.lower()))[:limit]
    return sorted(ranked, key=str.lower), max(0, len(paths) - limit)


def doc_paths(paths: list[str], readme: str | None, focus: str | None = None,
              focus_file: bool = False) -> list[str]:
    """The files worth reading besides the README, best first: the focus (a /blob link's file, of any kind, or
    the markdown in a /tree link's folder, even under tests/ or examples/), the index file of docs/, root docs,
    then the rest of docs/ (shallow first). Otherwise tests, examples and vendored code are left out."""
    focus = (focus or "").strip("/") or None

    def under_focus(p: str) -> bool:
        return bool(focus) and (p == focus or p.startswith(focus + "/"))  # whole segments: not website2/

    def rank(p: str):
        folder, _, name = p.rpartition("/")
        root = "/" not in p
        in_docs = p.lower().startswith(DOC_DIRS)
        # an index file leads only at the top of the focus folder or of docs/: docs/a/b/README.md is just a doc
        top = folder == focus if under_focus(p) else in_docs and "/" not in folder
        index = top and name.lower().split(".")[0] in INDEX_NAMES
        return (not under_focus(p), p != focus, not index, not root, not in_docs, p.count("/"), p.lower())

    out = [p for p in paths if p.lower().endswith(MARKDOWN_EXT) and p != readme and (
        under_focus(p) or not SKIP_DIRS.search(p) and (
            ("/" not in p and not SKIP_ROOT_DOCS.match(p)) or p.lower().startswith(DOC_DIRS)))]
    if focus_file and focus != readme and focus not in out:
        out.append(focus)  # any kind of file (a /blob link to code), even one a cut tree listing misses
    return sorted(out, key=rank)


def readme_of(gh: GitHub, repo: str, sha: str) -> tuple[str | None, str]:
    try:
        r = gh.get(f"repos/{repo}/readme?ref={sha}")
    except NotFound:
        return None, ""
    text = base64.b64decode(r.get("content") or "").decode("utf-8", errors="replace")
    return r.get("path"), text


def fetch_docs(gh: GitHub, repo: str, sha: str, paths: list[str]) -> list[tuple[str, str, str]]:
    """[(path, text, cut note)] within DOC_BUDGET characters; at most DOC_TRIES files are fetched, and
    DOC_FAILS failures in a row end it (every file of a repo that can't be read fails the same way)."""
    docs, used, fails = [], 0, 0
    for i, p in enumerate(paths):
        if used >= DOC_BUDGET:
            break
        if i >= DOC_TRIES:
            log(f"docs: stopped after {DOC_TRIES} files ({len(paths) - i} more)")
            break
        try:
            text = gh.raw_file(repo, sha, p)
        except SkillError as e:
            log(f"skipped {p}: {e}")
            fails += 1
            if fails >= DOC_FAILS:
                log(f"docs: {fails} files in a row could not be read, stopped")
                break
            continue
        fails = 0
        if "\x00" in text[:8000]:
            log(f"skipped {p}: a binary file")
            continue
        text, note = cut(text, min(DOC_MAX, DOC_BUDGET - used))
        docs.append((p, text, note))
        used += len(text)
    return docs


def cut(text: str, limit: int) -> tuple[str, str]:
    """(at most `limit` characters, cut at a line end; a note on what was cut, or "")."""
    if len(text) <= limit:
        return text, ""
    head = text[:limit].rsplit("\n", 1)[0]
    return head, f"*[cut: {len(text) - len(head):,} more characters in the file]*"


def code_file(text: str, repo: str, sha: str, path: str, note: str = "") -> str:
    """A non-markdown file (a /blob link to code): numbered lines in a fence, and how to link one of them."""
    blob = f"https://github.com/{repo}/blob/{sha}/{urllib.parse.quote(path)}"
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    width = len(str(len(lines)))
    lang = LANGS.get(path.rsplit(".", 1)[-1].lower(), "") if "." in path.rsplit("/", 1)[-1] else ""
    fence = "~" * max([3] + [len(m) + 1 for m in re.findall(r"~{3,}", text)])  # longer than any ~~~ inside
    rows = [f"[source]({blob}) · link line n as `[L<n>]({blob}#L<n>)`", "", fence + lang,
            *(f"{n:>{width}}  {line}" for n, line in enumerate(lines, 1)), fence]
    return "\n".join(rows) + (f"\n\n{note}" if note else "")


# ---------------------------------------------------------------- content


def render_repo(meta: dict, facts: dict, readme: tuple[str | None, str], tree: tuple[list[str], int, bool],
                docs: list[tuple[str, str]]) -> str:
    info, ex = facts["info"], meta["extras"]
    ref = ex.get("ref") or ex["default_branch"]
    repo, sha = meta["id"], facts["sha"]
    rows = [f"# {repo}", "", f"- url: {meta['url']}"]
    release = ex.get("release")
    for label, value in (("description", info.get("description")), ("homepage", info.get("homepage")),
                         ("stars", f"{info.get('stargazers_count', 0):,} · forks {info.get('forks_count', 0):,}"
                                   f" · open issues {info.get('open_issues_count', 0):,}"),
                         ("license", ex.get("license")), ("languages", ", ".join(ex.get("languages") or [])),
                         ("latest release", release and f"{release['tag']} ({release['date']})"),
                         ("created", meta.get("published")), ("last push", ex.get("pushed_at")),
                         ("topics", ", ".join(ex.get("topics") or [])),
                         ("commit", f"{ref} @ {sha[:12]} ({ex.get('commit_date') or '?'})"
                                    + ("" if ref == ex["default_branch"] else
                                       f", the link's ref; default branch {ex['default_branch']}")),
                         ("archived", "yes: read-only, no longer maintained" if info.get("archived") else None),
                         ("fork of", ex.get("fork_of")), ("focus", ex.get("focus_path")),
                         ("repo pack", ex.get("pack_file") and f"{ex['pack_file']} ({ex['pack_words']:,} words,"
                                                              f" commit {(ex.get('pack_sha') or '?')[:12]})")):
        if value:
            rows.append(f"- {label}: {value}")
    path, text = readme
    text, note = cut(text, README_MAX)
    rows += ["", f"## README ({path})" if path else "## README", "",
             anchor_file(text, repo, sha, path, note=note) if path else "*No README.*"]
    shown, more, truncated = tree
    rows += ["", "## Files", "", "```", *shown, "```"]
    if more or truncated:
        rows.append(f"\n*{more:,} more files{' (GitHub cut the listing short)' if truncated else ''}.*")
    if docs:
        rows += ["", "## Docs"]
        for p, text, note in docs:
            body = anchor_file(text, repo, sha, p, demote=3, note=note) if p.lower().endswith(MARKDOWN_EXT) \
                else code_file(text, repo, sha, p, note)
            rows += ["", f"### {p}", "", body]
    return "\n".join(rows) + "\n"


# ---------------------------------------------------------------- --deep


def pack(url: str, folder: Path, size_kb: int, sha: str) -> tuple[str, int]:
    """repomix's pack of the whole repo at commit `sha` (the one the anchors point at) -> <folder>/repo-pack.md;
    (file name, words)."""
    require("npx")
    if size_kb > BIG_REPO_KB:
        log(f"the repo is {size_kb / 1000:,.0f} MB: packing it takes a while and the pack can be very large")
    out = folder / "repo-pack.md"
    log(f"packing the repo with {REPOMIX} (--deep)")
    try:
        p = subprocess.run(["npx", "-y", REPOMIX, "--remote", url, "--remote-branch", sha, "--style", "markdown",
                            "--compress", "--no-security-check", "--ignore", PACK_IGNORE, "-o", str(out)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=DEEP_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise SkillError(f"repomix timed out after {DEEP_TIMEOUT}s; summarize without --deep")
    if p.returncode != 0 or not out.exists():
        err = (p.stderr.strip() or p.stdout.strip()).splitlines()
        raise SkillError(f"repomix failed: {err[-1] if err else p.returncode}; summarize without --deep")
    words = len(out.read_text(encoding="utf-8", errors="replace").split())
    if words > BIG_PACK_WORDS:
        log(f"the pack has {words:,} words: search it for the parts that matter instead of reading it whole")
    return out.name, words


# ---------------------------------------------------------------- main


def prepare_repo(gh: GitHub, r: dict, deep: bool, refresh: bool) -> int:
    ref_path = r.get("ref_path") or None  # a /tree or /blob link: <ref>/<path>, split once the refs are known
    existing = find_by_id("github", r["repo"])
    old = read_json(existing / "metadata.json") if existing else {}
    old_ex = old.get("extras") or {}
    fresh_enough = not refresh and (old_ex.get("pack_file") or not deep) and old_ex.get("ref_path") == ref_path
    if existing and (existing / "content.md").exists() and fresh_enough:
        log(f"reusing: {existing} (pass --refresh to refetch)")
        return print_envelope(existing, old, reused=True)

    facts = repo_facts(gh, r["repo"], ref_path)
    info, sha, focus = facts["info"], facts["sha"], facts["path"]
    repo = info.get("full_name") or r["repo"]  # GitHub's spelling: the URL's may differ in case, or be renamed
    if repo != r["repo"] and not existing:
        existing = find_by_id("github", repo)
        old = read_json(existing / "metadata.json") if existing else {}
        old_ex = old.get("extras") or {}
    if ref_path:
        log(f"reading {repo} at {facts['ref']} ({sha[:12]}){f', {focus} first' if focus else ''}")
    readme = readme_of(gh, repo, sha)
    paths, truncated = tree_paths(gh, repo, sha)
    shown, more = shown_tree(paths)
    docs = fetch_docs(gh, repo, sha, doc_paths(paths, readme[0], focus, focus_file=r["kind"] == "blob"))
    log(f"{gh.mode}: {len(paths)} files, README {len(readme[1]):,} chars, {len(docs)} docs")
    release = facts["release"]
    # a pack is of one commit: keep an old one only while the anchors still point at that commit
    keep_pack = old_ex.get("pack_file") and old_ex.get("pack_sha") == sha
    extras = {k: v for k, v in {
        "kind": "repo", "stars": info.get("stargazers_count"), "forks": info.get("forks_count"),
        "license": (info.get("license") or {}).get("spdx_id"), "languages": language_share(facts["languages"]),
        "release": release and {"tag": release.get("tag_name"), "date": (release.get("published_at") or "")[:10]},
        "pushed_at": (info.get("pushed_at") or "")[:10] or None, "topics": info.get("topics") or None,
        "homepage": info.get("homepage") or None, "default_branch": info.get("default_branch"), "sha": sha,
        "ref": facts["ref"] if ref_path else None, "ref_path": ref_path,
        "commit_date": (facts["commit_date"] or "")[:10] or None, "archived": info.get("archived") or None,
        "fork_of": (info.get("parent") or {}).get("full_name"), "focus_path": focus, "files": len(paths),
        "docs": [p for p, _, _ in docs] or None, "api": gh.mode,
        "pack_file": old_ex.get("pack_file") if keep_pack else None,
        "pack_words": old_ex.get("pack_words") if keep_pack else None,
        "pack_sha": sha if keep_pack else None,
        "aliases": sorted({*old_ex.get("aliases", []), r["repo"]} - {repo}) or None,
    }.items() if v is not None}
    meta = {
        "source": "github", "id": repo, "url": f"https://github.com/{repo}", "title": repo,
        "author": (info.get("owner") or {}).get("login"), "published": (info.get("created_at") or "")[:10] or None,
        "fetched": datetime.now().isoformat(timespec="seconds"), "site": "GitHub", "word_count": 0,
        "duration": None, "extractor": gh.mode, "content_file": "content.md", "extras": extras,
    }
    folder = existing or unique_dir(meta)
    folder.mkdir(parents=True, exist_ok=True)
    log(f"{'refreshing' if existing else 'folder'}: {folder}")
    if deep:
        extras["pack_file"], extras["pack_words"] = pack(meta["url"], folder, info.get("size") or 0, sha)
        extras["pack_sha"] = sha
    elif old_ex.get("pack_file") and not keep_pack:
        (folder / old_ex["pack_file"]).unlink(missing_ok=True)
        log(f"dropped {old_ex['pack_file']}: it packs an older commit (pass --deep to pack this one)")
    content = render_repo(meta, facts, readme, (shown, more, truncated), docs)
    meta["word_count"] = len(content.split())
    (folder / "content.md").write_text(content, encoding="utf-8")
    meta = update_json(folder / "metadata.json", meta | {"prepared_at": old.get("prepared_at") or meta["fetched"]})
    return print_envelope(folder, meta, reused=bool(existing))


def print_envelope(folder: Path, meta: dict, reused: bool) -> int:
    ex = meta.get("extras") or {}
    fields = {"repo": meta["id"].split("#")[0], "stars": ex.get("stars"), "files": ex.get("files"),
              "pack_file": str(folder / ex["pack_file"]) if ex.get("pack_file") else None,
              "pack_words": ex.get("pack_words"), "api": ex.get("api")}
    if ex.get("kind") != "repo":
        fields = {"repo": meta["id"].split("#")[0], "number": ex.get("number"), "state": ex.get("state"),
                  "comments": ex.get("comments"), "api": ex.get("api")}
    print(json.dumps(envelope(folder, meta, ex.get("kind") or "repo", reused=reused, **fields),
                     indent=2, ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--deep", action="store_true", help="also pack the whole repo with repomix (needs npx)")
    ap.add_argument("--refresh", action="store_true", help="refetch even if it was prepared before")
    args = ap.parse_args(argv)
    r = route(args.url)
    if r["source"] != "github":
        raise SkillError(f"{args.url} is a {r['source']} input, not a GitHub URL")
    gh = GitHub()
    if r["kind"] in ("repo", "blob"):  # a file or folder link: the repo, with that path read first
        return prepare_repo(gh, r, args.deep, args.refresh)
    from thread import prepare_thread
    folder, meta, reused = prepare_thread(gh, r, args.refresh)
    return print_envelope(folder, meta, reused)


if __name__ == "__main__":
    run_main(main)

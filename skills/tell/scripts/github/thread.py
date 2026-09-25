#!/usr/bin/env python3
"""A GitHub issue, pull request or discussion in discussion shape (called by prepare.py).

Issue: the issue, its comments. Pull request: also the branch, the diff size, the changed files, the reviews
(approved / changes requested, with their text) and the review comments on lines of the diff. Discussion (GraphQL:
gh, or GITHUB_TOKEN): the post, its comments and their replies, the answer marked.
content.md: a header, `## <Issue|Pull request|Discussion>` with the opening post, (`## Files changed`), then
`## Comments` with one line per comment in time order:
`- **author** [→](<comment url>) (<date>[, reply to <author>][, on <path>:<line>][, <review state>]): text`.
Folder: <root>/repos/github/<owner>/<repo>/<issues|pulls|discussions>/<n>-<title>/.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))  # _common + the shared steps

from _common import find_by_id, log, read_json, unique_dir, update_json
from client import NotFound

FILES_MAX = 100  # changed files listed for a pull request
DISCUSSION = """query($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    discussion(number: $number) {
      number title body url createdAt closed upvoteCount
      author { login } category { name } answer { id }
      labels(first: 20) { nodes { name } }
      comments(first: 50, after: $after) {
        totalCount pageInfo { hasNextPage endCursor }
        nodes {
          id url body createdAt upvoteCount isAnswer author { login }
          replies(first: 100) { totalCount nodes { id url body createdAt upvoteCount author { login } } }
        }
      }
    }
  }
}"""
REVIEW_STATES = {"APPROVED": "approved", "CHANGES_REQUESTED": "changes requested", "COMMENTED": "review",
                 "DISMISSED": "review, dismissed"}
LABELS = {"issue": "Issue", "pull": "Pull request", "discussion": "Discussion"}
HTML_URL = re.compile(r"^https://github\.com/([^/]+/[^/]+)/(?:issues|pull|discussions)/(\d+)")


# ---------------------------------------------------------------- text


def clean(body: str | None) -> str:
    """A GitHub markdown body without HTML comments (issue/PR templates) and CRs, <img> tags as markdown images,
    its headings as bold lines
    (a heading inside a list item would break the file's own sections), trimmed."""
    text = re.sub(r"<!--.*?-->", "", (body or "").replace("\r\n", "\n"), flags=re.S)
    text = re.sub(r"<img\b[^>]*?\bsrc=\"([^\"]+)\"[^>]*>", r"![image](\1)", text)  # pasted screenshots
    out, fence = [], False
    for line in text.split("\n"):
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
        elif not fence and (m := re.match(r" {0,3}#{1,6}\s+(.*?)\s*#*\s*$", line)):
            line = f"**{m.group(1)}**"
        out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def indent(text: str, prefix: str = "  ") -> str:
    """A comment's later lines, indented to stay inside its list item."""
    return "\n".join(line if i == 0 or not line else prefix + line for i, line in enumerate(text.splitlines()))


def day(ts: str | None) -> str:
    return (ts or "")[:10] or "?"


def login(user: dict | None) -> str:
    return (user or {}).get("login") or "ghost"  # GitHub's name for a deleted account


def comment_line(c: dict) -> str:
    """One `- **author** [→](url) (date, notes): text` line of the ## Comments list."""
    notes = [day(c["date"]), *c.get("notes", [])]
    text = clean(c["body"]) or "*(no text)*"
    return f"- **{c['author']}** [→]({c['url']}) ({', '.join(notes)}): " + indent(text)


# ---------------------------------------------------------------- fetch


def issue_comments(gh, repo: str, number: int) -> list[dict]:
    return [{"author": login(c.get("user")), "url": c.get("html_url"), "date": c.get("created_at"),
             "body": c.get("body"), "reactions": (c.get("reactions") or {}).get("total_count") or 0}
            for c in gh.get_all(f"repos/{repo}/issues/{number}/comments")]


def pull_extras(gh, repo: str, number: int) -> tuple[dict, list[dict], list[dict]]:
    """(the pull request's facts, its reviews and review comments as comments, its changed files)."""
    pr = gh.get(f"repos/{repo}/pulls/{number}")
    out: list[dict] = []
    for r in gh.get_all(f"repos/{repo}/pulls/{number}/reviews"):
        if r.get("state") == "PENDING" or not r.get("submitted_at"):
            continue  # a draft review, not sent yet (only its author sees it)
        state = REVIEW_STATES.get(r.get("state"), (r.get("state") or "review").lower())
        if not clean(r.get("body")) and state == "review":
            continue  # the container of line comments, listed below on their own
        out.append({"author": login(r.get("user")), "url": r.get("html_url"), "date": r.get("submitted_at"),
                    "body": r.get("body"), "notes": [state]})
    by_id: dict[int, str] = {}
    for c in gh.get_all(f"repos/{repo}/pulls/{number}/comments"):
        author = login(c.get("user"))
        by_id[c["id"]] = author
        line = c.get("line") or c.get("original_line")
        notes = [f"on {c.get('path')}{f':{line}' if line else ''}"]
        if c.get("in_reply_to_id") in by_id:
            notes.insert(0, f"reply to {by_id[c['in_reply_to_id']]}")
        out.append({"author": author, "url": c.get("html_url"), "date": c.get("created_at"),
                    "body": c.get("body"), "notes": notes})
    files = gh.get_all(f"repos/{repo}/pulls/{number}/files", max_pages=FILES_MAX // 100 or 1)
    facts = {"merged": pr.get("merged"), "merged_at": day(pr.get("merged_at")) if pr.get("merged_at") else None,
             "draft": pr.get("draft") or None, "head": (pr.get("head") or {}).get("label"),
             "base": (pr.get("base") or {}).get("ref"), "additions": pr.get("additions"),
             "deletions": pr.get("deletions"), "changed_files": pr.get("changed_files"),
             "head_sha": (pr.get("head") or {}).get("sha")}
    return facts, out, [{"path": f.get("filename"), "status": f.get("status"), "additions": f.get("additions"),
                         "deletions": f.get("deletions")} for f in files]


def canonical(html_url: str | None, repo: str, number: int) -> tuple[str, int]:
    """(owner/repo, number) by GitHub's spelling from an item's html_url: the URL's case may differ, and a
    transferred issue lives on in another repo under another number."""
    m = HTML_URL.match(html_url or "")
    return (m.group(1), int(m.group(2))) if m else (repo, number)


def fetch_issue(gh, r: dict) -> dict:
    """An issue or pull request: {post, comments, files, facts}."""
    issue = gh.get(f"repos/{r['repo']}/issues/{r['number']}")
    repo, number = canonical(issue.get("html_url"), r["repo"], r["number"])
    kind = "pull" if issue.get("pull_request") else "issue"  # /issues/N of a PR is the PR
    comments = issue_comments(gh, repo, number)
    facts = {"kind": kind, "number": number, "state": issue.get("state"),
             "state_reason": issue.get("state_reason"), "closed_at": day(issue.get("closed_at"))
             if issue.get("closed_at") else None,
             "labels": [lb.get("name") for lb in issue.get("labels") or []] or None,
             "reactions": (issue.get("reactions") or {}).get("total_count") or None,
             "assignees": [login(a) for a in issue.get("assignees") or []] or None,
             "milestone": (issue.get("milestone") or {}).get("title")}
    files: list[dict] = []
    if kind == "pull":
        pr, review, files = pull_extras(gh, repo, number)
        facts |= pr
        comments += review
    comments.sort(key=lambda c: c.get("date") or "9999")  # an undated one last
    post = {"author": login(issue.get("user")), "url": issue.get("html_url"), "date": issue.get("created_at"),
            "body": issue.get("body")}
    return {"title": issue.get("title"), "url": issue.get("html_url"), "post": post, "comments": comments,
            "files": files, "facts": facts, "repo": repo}


def fetch_discussion(gh, r: dict) -> dict:
    owner, name = r["repo"].split("/", 1)
    nodes, after, d = [], None, None
    while True:
        data = gh.graphql(DISCUSSION, owner=owner, name=name, number=r["number"], **({"after": after} if after else {}))
        d = ((data.get("repository") or {}).get("discussion"))
        if not d:
            raise NotFound(f"no discussion #{r['number']} in {r['repo']}")
        page = d["comments"]
        nodes += page["nodes"]
        if not page["pageInfo"]["hasNextPage"] or len(nodes) >= 1000:
            break
        after = page["pageInfo"]["endCursor"]
    repo, number = canonical(d.get("url"), r["repo"], r["number"])
    answer = (d.get("answer") or {}).get("id")
    comments = []
    for c in nodes:
        author = login(c.get("author"))
        notes = ["the answer"] if c.get("isAnswer") or c.get("id") == answer else []
        comments.append({"author": author, "url": c.get("url"), "date": c.get("createdAt"), "body": c.get("body"),
                         "notes": notes + votes(c)})
        replies = c.get("replies") or {}
        for rp in replies.get("nodes") or []:
            comments.append({"author": login(rp.get("author")), "url": rp.get("url"), "date": rp.get("createdAt"),
                             "body": rp.get("body"), "notes": [f"reply to {author}", *votes(rp)], "reply": True})
        if (replies.get("totalCount") or 0) > len(replies.get("nodes") or []):
            log(f"{c.get('url')}: only the first {len(replies['nodes'])} of {replies['totalCount']} replies")
    facts = {"kind": "discussion", "number": number, "state": "closed" if d.get("closed") else "open",
             "category": (d.get("category") or {}).get("name"), "answered": bool(answer) or None,
             "labels": [lb["name"] for lb in (d.get("labels") or {}).get("nodes") or []] or None,
             "upvotes": d.get("upvoteCount") or None}
    if d["comments"]["totalCount"] > len(nodes):
        log(f"only the first {len(nodes)} of {d['comments']['totalCount']} comments")
    post = {"author": login(d.get("author")), "url": d.get("url"), "date": d.get("createdAt"), "body": d.get("body")}
    return {"title": d.get("title"), "url": d.get("url"), "post": post, "comments": comments, "files": [],
            "facts": facts, "repo": repo}


def votes(c: dict) -> list[str]:
    n = c.get("upvoteCount") or 0
    return [f"{n} upvote{'s' if n != 1 else ''}"] if n else []


# ---------------------------------------------------------------- content


def render(meta: dict, t: dict) -> str:
    f, kind = t["facts"], t["facts"]["kind"]
    state = f.get("state")
    if kind == "pull":
        state = "merged" if f.get("merged") else "draft" if f.get("draft") and state == "open" else state
    elif f.get("state_reason") and state == "closed":
        state = f"closed ({f['state_reason'].replace('_', ' ')})"
    rows = [f"# {t['title']} ({meta['id']})", "", f"- url: {t['url']}"]
    n_files = f.get("changed_files") or 0
    diff = f"+{f.get('additions', 0):,} −{f.get('deletions', 0):,} in {n_files:,} file{'s' if n_files != 1 else ''}"
    for label, value in (("kind", LABELS[kind].lower()), ("state", state),
                         ("opened by", f"{t['post']['author']} on {day(t['post']['date'])}"),
                         ("closed", f.get("closed_at") if kind != "pull" or not f.get("merged") else None),
                         ("merged", f.get("merged_at")), ("branch", f.get("head") and f"{f['head']} → {f['base']}"),
                         ("diff", diff if kind == "pull" else None), ("category", f.get("category")),
                         ("answered", "yes" if f.get("answered") else None),
                         ("labels", ", ".join(f.get("labels") or [])), ("milestone", f.get("milestone")),
                         ("assignees", ", ".join(f.get("assignees") or [])), ("reactions", f.get("reactions")),
                         ("upvotes", f.get("upvotes")),
                         ("comments", len(t["comments"]))):
        if value:
            rows.append(f"- {label}: {value}")
    rows += ["", f"## {LABELS[kind]}", "", comment_line(t["post"] | {"notes": []})]
    if t["files"]:
        rows += ["", "## Files changed", ""]
        rows += [f"- `{x['path']}` ({x['status']}, +{x['additions']} −{x['deletions']})" for x in t["files"]]
        if (f.get("changed_files") or 0) > len(t["files"]):
            rows.append(f"- *{f['changed_files'] - len(t['files'])} more files*")
    rows += ["", "## Comments", ""]
    rows += [comment_line(c) for c in t["comments"]] or ["*No comments yet.*"]
    return "\n".join(rows) + "\n"


# ---------------------------------------------------------------- main


def prepare_thread(gh, r: dict, refresh: bool) -> tuple[Path, dict, bool]:
    """(folder, metadata, reused) of an issue, pull request or discussion. Its id is GitHub's spelling
    (`owner/repo#n` from the API); the URL's, when it differs, is kept as an alias."""
    existing = find_by_id("github", r["id"])
    if existing and (existing / "content.md").exists() and not refresh:
        log(f"reusing: {existing} (pass --refresh to refetch)")
        return existing, read_json(existing / "metadata.json"), True
    t = fetch_discussion(gh, r) if r["kind"] == "discussion" else fetch_issue(gh, r)
    f = t["facts"]
    repo = t["repo"]
    tid = f"{repo}#{f['number']}"
    if tid != r["id"] and not existing:
        existing = find_by_id("github", tid)
    log(f"{gh.mode}: {LABELS[f['kind']].lower()} with {len(t['comments'])} comments")
    old = read_json(existing / "metadata.json") if existing else {}
    aliases = sorted({*((old.get("extras") or {}).get("aliases") or []), r["id"]} - {tid}) or None
    extras = {k: v for k, v in (f | {"comments": len(t["comments"]), "repo": repo, "api": gh.mode,
                                     "files": len(t["files"]) or None, "aliases": aliases}).items()
              if v is not None}
    meta = {
        "source": "github", "id": tid, "url": t["url"] or r["url"], "title": t["title"] or tid,
        "author": t["post"]["author"], "published": day(t["post"]["date"]),
        "fetched": datetime.now().isoformat(timespec="seconds"), "site": "GitHub", "word_count": 0,
        "duration": None, "extractor": gh.mode, "content_file": "content.md", "extras": extras,
    }
    content = render(meta, t)
    meta["word_count"] = len(content.split())
    folder = existing or unique_dir(meta)
    folder.mkdir(parents=True, exist_ok=True)
    log(f"{'refreshing' if existing else 'folder'}: {folder}")
    (folder / "content.md").write_text(content, encoding="utf-8")
    meta = update_json(folder / "metadata.json", meta | {"prepared_at": old.get("prepared_at") or meta["fetched"]})
    return folder, meta, bool(existing)

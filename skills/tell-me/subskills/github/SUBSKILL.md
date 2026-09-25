# github

GitHub repositories, and their issues, pull requests and discussions.

- **Repo** (`github.com/<owner>/<repo>`, also a `/tree/<ref>/<path>` or `/blob/<ref>/<path>` link, which reads that
  path first): `content.md` has a header (description, stars, license, languages, latest release, last push,
  topics, the commit it was read at), `## README`, `## Files` (the first 200 paths, shallow first) and `## Docs`
  (root markdown like ARCHITECTURE.md and `docs/`, up to a size budget).
- **Issue / pull request / discussion**: a header (state, who opened it, labels, for a PR the branch and diff
  size), the opening post under `## Issue`, `## Pull request` or `## Discussion`, `## Files changed` for a PR, then
  `## Comments`, one line per comment in time order:

  ```
  - **author** [→](<comment url>) (<date>[, reply to <author>][, on <path>:<line>][, approved]): text
  ```

## Flags

```bash
python3 $S/shared/prepare.py "<github url>" [--deep] [--refresh]
```

- The API goes through `gh` when it is installed and logged in (5000 requests/hour), else plain HTTPS (60
  requests/hour, or 5000 with `GITHUB_TOKEN` set); the envelope's `api` says which. On a rate-limit error tell the
  user to run `gh auth login`. Discussions need GraphQL: `gh` or `GITHUB_TOKEN`.
- `--deep` also packs the whole repository with repomix (`npx`, pinned) into `repo-pack.md` next to
  `content.md`; the envelope's `pack_file` and `pack_words` point at it. Use it when the user asks how the code
  works (architecture, a specific mechanism), not for "what is this repo". It clones the repo: for a big one
  (the script warns) it takes minutes and the pack can exceed what you can read, so read it selectively (search
  it for the files and symbols that matter).
- An item prepared before is reused (repos by `owner/repo`, threads by `owner/repo#n`); `--refresh` refetches it
  into the same folder. A repo link with a different focus path is refetched.
- An `/issues/N` link to a pull request is prepared as the pull request.

## Anchor links

- Repo: every paragraph and list item of the README and docs starts with `[L<n>]`, a link to that line of the
  file at the commit it was read at (`blob/<sha>/<path>?plain=1#L<n>`), and every heading ends with `[#]` (GitHub's
  heading anchor). Links stay valid when the repo changes. Name files and folders from `## Files` in backticks.
- Threads: `[→]` is the permalink of the post or comment. Copy the links, never build them.

## Reading

**Repo.** Answer, in this order: what it is and the problem it solves (one or two sentences, from the
description and the README's opening), who it is for, how to install and use it (commands verbatim), how it is
built (the layout from `## Files`, the main modules, the docs' architecture notes; with `--deep`, from the pack),
and how alive it is (stars, the last push and release dates, archived or not). Say which claims come from the
README (marketing) and which from docs or code. A README that is mostly badges, a logo or a link elsewhere:
say so and lean on the docs and the file tree.

**Issue / pull request / discussion.** Summarize the opening post first (the problem, the proposal, or the
change), then follow [subskills/shared/discussion.md](../shared/discussion.md) for the comments: themes with
attributed verbatim quotes, then check them with `check_quotes.py`. Then add what a reader needs:
- **Issue:** is it confirmed, is there a workaround (quote it), and what is the status (open, closed as completed
  or as not planned, linked fix).
- **Pull request:** what changes (from `## Files changed` and the description), what reviewers asked for and
  whether it was addressed (the `on <path>:<line>` comments and review verdicts), merged or not.
- **Discussion:** the accepted answer when there is one (`the answer`), otherwise the most upvoted replies.
- Maintainers and the author carry more weight than drive-by comments: say who is who when the thread shows it.
  Bots (`[bot]` logins: CI, dependabot) are context, not voices; skip them unless they report the failure that
  matters.

## Similar repos (related section)

```bash
python3 $S/github/related.py "<dir>" [--query "<3-5 words on what it does>"]
```

It searches GitHub for the repo's topics (and your query; required when the repo has no topics), drops the repo
and forks, ranks by shared topics then stars, and marks repos already summarized. Pick 3-5 real alternatives or
complements (not merely popular repos that share a generic topic like `cli`), each with one line on how it
differs; add `([summary](<path>))` when the script gives one. For a thread, the related section is the repo
itself plus any issues or PRs the thread links as duplicates or fixes.

## Page and files

The page header shows the owner, the date and a link to GitHub; the full `content.md` is in the collapsed
**Repository** section below the summary. Repos live in `repos/github/<owner>/<repo>/`, threads in
`repos/github/<owner>/<repo>/<issues|pulls|discussions>/<n>-<title>/`, each with `summary.md`, `summary.html`,
`content.md`, `metadata.json` (`extras`: stars, license, languages, release, topics, sha, docs, api, pack_file;
threads: number, state, labels, comments, merged, additions, deletions) and `repo-pack.md` after `--deep`.

## Scripts (`scripts/github/`)

| Script | Does |
|---|---|
| `prepare.py` | repo: facts + README + tree + docs → `content.md` with line anchors; `--deep` repomix pack; threads via `thread.py` |
| `thread.py` | issue / pull request (+ reviews, line comments, files) / discussion (GraphQL) → discussion-shaped `content.md` |
| `related.py` | similar repos by topic / query search, library summaries marked |
| `client.py` | `gh api` or REST (token or anonymous), rate-limit messages; `client.py <api path>` prints raw JSON |
| `anchors.py` | `[L<n>]` line anchors and `[#]` heading anchors pinned to a commit |

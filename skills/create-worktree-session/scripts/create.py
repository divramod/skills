#!/usr/bin/env python3
"""Start an agent session in the repository's first free and clean worktree slot.

  create.py [--repo DIR] [--agent claude|codex|opencode] [--model ID] [--tmux] [--prompt TEXT] [--exact]
            [--from NN] [--base REV] [--lead "<lead-slot> <plan> <step>"] [--min-free-gb 50]

The slot, counting from 01: no agent session runs in it (no live agent of the repository, no live terminal host
of its worktree, no window of tmux session hal-<repo>), and its worktree is clean or missing: plans/CURRENT_PLAN
names nothing, no uncommitted changes, no commits not on main, no landing in the merge queue (behind main is
fine: the first prompt runs /mfm). The agent starts detached through `hal2-cli-git worktree run <NN> --detach`, in
a hal2 terminal host (`--tmux`: a window of hal-<repo>), with a new session whose first prompt runs /mfm, then the
given prompt (`--exact`: the prompt as given, without /mfm). Prints JSON: slot, pane, worktree, the attach
command and the slots skipped for their work. Exit 2 when a hal2 CLI is missing, 1 when no slot is left.

A parallel plan's subservant (skills plan 0013): `--from NN` starts the search at slot NN (30 for subservants);
`--base REV` branches the slot from REV instead of main (`git fetch origin` first for `origin/...`; `git branch -f
NN REV` for a new slot, `git reset --hard REV` in a reused clean one; a slot whose leftover branch NN holds commits
neither in REV nor on origin's default branch is skipped); `--lead` writes the marker `plans/LEAD` and
`plans/CURRENT_PLAN` (into the clone's info/exclude when the repo does not ignore them) before the agent starts (a
new slot's worktree is created first, as hal2 creates it) and implies `--exact` (no /mfm: the lead's branch is the
base). A new worktree needs `--min-free-gb` free disk (default 50).
"""
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

GONE = {"ended", "failed"}
# What hal2-agents' spawn drops, so the agent is no child of this tmux pane, terminal host or Claude session.
DROPPED_ENV = ("TMUX", "TMUX_PANE", "HAL2_TERMINAL", "CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION",
               "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_BRIDGE_SESSION_ID", "CLAUDE_CODE_MESSAGING_SOCKET",
               "CLAUDE_CODE_MESSAGING_TOKEN", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_EXECPATH",
               "CLAUDE_CODE_SESSION_ATTENDED", "CLAUDE_PID", "CLAUDE_EFFORT")


def die(message: str, code: int = 1) -> NoReturn:
    print(f"create.py: {message}", file=sys.stderr)
    sys.exit(code)


def need(tool: str) -> None:
    if not shutil.which(tool):
        die(f"{tool} is missing: run scripts/install-prerequisites.sh (needs hal2)", 2)


def run(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    need(args[0])
    r = subprocess.run(list(args), cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        die(f"{' '.join(args[:3])} failed: {(r.stderr or r.stdout).strip()}")
    return r.stdout if r.returncode == 0 else ""


def main_checkout(repo: Path) -> Path:
    out = run("git", "worktree", "list", "--porcelain", cwd=repo)
    first = out.splitlines()[0] if out else ""
    return Path(first.split(" ", 1)[1]) if first.startswith("worktree ") else repo


def slot_of(name: str) -> str | None:
    return name if len(name) == 2 and name.isdigit() else None


def taken(repo: Path) -> set[str]:
    """Slots a session holds: a live agent, a live terminal host of the worktree, a window of hal-<repo>."""
    agents = json.loads(run("hal2-cli-agents", "list", "--json"))
    agents = agents if isinstance(agents, list) else agents.get("agents", [])
    slots = {a.get("slot") for a in agents if a.get("state") not in GONE and a.get("project")
             and Path(a["project"]).resolve() == repo.resolve()}
    for host in json.loads(run("hal2-cli-agents", "terminal", "list", "--json") or "[]"):
        worktree = Path(host.get("worktree") or "/")
        if host.get("alive") and worktree.parent.name == repo.name:
            slots.add(worktree.name)
    if shutil.which("tmux"):
        windows = run("tmux", "list-windows", "-t", f"hal-{repo.name}", "-F", "#W", check=False)
        slots |= set(windows.split())
    return {s for s in slots if s and slot_of(s)}


def work(entry: dict, landing: str | None) -> str | None:
    """Why a worktree holds work, or None when it is clean."""
    if entry.get("plan"):
        return f"works on {entry['plan']}"
    if entry.get("dirty"):
        return "uncommitted changes"
    if entry.get("main_ahead"):
        return f"{entry['main_ahead']} commit{'s' if entry['main_ahead'] != 1 else ''} not on main"
    return f"its landing is {landing} in the merge queue" if landing else None


def default_branch(repo: Path) -> str:
    """origin's default branch as `origin/<name>`, else the local main or master."""
    head = run("git", "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD", cwd=repo, check=False).strip()
    if head:
        return head.removeprefix("refs/remotes/")
    for ref in ("origin/main", "origin/master", "main", "master"):
        if run("git", "rev-parse", "--verify", "--quiet", ref, cwd=repo, check=False):
            return ref
    return "HEAD"


def leftover(repo: Path, slot: str, base: str) -> str | None:
    """Why branch `slot` (no worktree) must not be moved to `base`: commits in neither `base` nor the default."""
    if not run("git", "rev-parse", "--verify", "--quiet", f"refs/heads/{slot}", cwd=repo, check=False):
        return None
    out = run("git", "rev-list", "--count", slot, "--not", base, default_branch(repo), cwd=repo, check=False)
    count = int(out.strip() or 0)
    return f"branch {slot} holds {count} commit{'s' if count != 1 else ''} in neither {base} nor main" if count else None


def choose(repo: Path, first: int = 1, base: str | None = None) -> tuple[str, list[dict], dict | None]:
    listed = json.loads(run("hal2-cli-git", "worktree", "list", "--json", cwd=repo)).get("worktrees", [])
    worktrees = {w["name"]: w for w in listed if not w.get("main")}
    queue = json.loads(run("hal2-cli-git", "worktree", "queue", "--json", cwd=repo)).get("queue", [])
    landings = {t.get("slot"): t.get("state") or "queued" for t in queue if t.get("repo") == repo.name}
    busy, skipped = taken(repo), []
    for n in range(first, 100):
        slot = f"{n:02d}"
        if slot in busy:
            continue
        if slot in worktrees:
            why = work(worktrees[slot], landings.get(slot))
        else:
            why = leftover(repo, slot, base) if base else None
        if why is None:
            return slot, skipped, worktrees.get(slot)
        skipped.append({"slot": slot, "why": why})
    die(f"no free and clean slot from {first:02d} to 99")


def free_gb(repo: Path) -> float:
    """Free disk where the worktrees live (hal2: ~/.hal/git/worktree)."""
    folder = Path.home() / ".hal" / "git" / "worktree"
    return shutil.disk_usage(folder if folder.exists() else repo).free / 2**30


def prepare(repo: Path, slot: str, entry: dict | None, base: str | None, min_gb: float) -> None:
    """Before the start: free disk for a new worktree, then the slot's branch at `base`."""
    if entry is None and free_gb(repo) < min_gb:
        needed = ("%f" % min_gb).rstrip("0").rstrip(".")
        die(f"only {free_gb(repo):.0f} GB free, a new worktree needs {needed} (--min-free-gb): prune a slot first")
    if not base:
        return
    if base.startswith("origin/"):
        run("git", "fetch", "--quiet", "origin", cwd=repo)
    if entry is None:
        run("git", "branch", "-f", slot, base, cwd=repo)
    else:
        run("git", "reset", "--quiet", "--hard", base, cwd=Path(entry["path"]))


def create_worktree(repo: Path, slot: str) -> Path:
    """Slot `slot`'s new worktree, as hal2's `worktree::ensure` makes it, before any agent runs in it.

    `worktree run --detach` creates it only inside the host it starts, after returning, and hal2 has no command
    that creates a given slot without an agent (`worktree new` takes the lowest free one), so a subservant's
    worktree is made here: `~/.hal/git/worktree/<repo>/<NN>` on branch NN (kept when it exists, else forked from
    the local default branch), published with `push -u` and its secrets revealed (both best effort)."""
    worktree = Path.home() / ".hal" / "git" / "worktree" / repo.name / slot
    run("git", "worktree", "prune", cwd=repo)
    if run("git", "rev-parse", "--verify", "--quiet", f"refs/heads/{slot}", cwd=repo, check=False):
        run("git", "worktree", "add", "--quiet", str(worktree), slot, cwd=repo)
    else:
        default = default_branch(repo).removeprefix("origin/")
        run("git", "worktree", "add", "--quiet", str(worktree), "-b", slot, default, cwd=repo)
    if "origin" in run("git", "remote", cwd=repo, check=False).split():
        run("git", "push", "--quiet", "-u", "origin", slot, cwd=worktree, check=False)
    if (worktree / ".secrets").is_dir() and shutil.which("hal2-cli-secrets"):
        run("hal2-cli-secrets", "reveal", "--repo", str(worktree), check=False)
    return worktree


def lead_parts(lead: str) -> list[str]:
    parts = lead.split()
    if len(parts) != 3:
        die(f"--lead needs '<lead-slot> <plan> <step>', not '{lead}'")
    return parts


def write_lead(worktree: Path, lead: str) -> None:
    """The subservant marker plans/LEAD (`<lead-slot> <plan> <step>`) and CURRENT_PLAN, both ignored."""
    parts = lead_parts(lead)
    (worktree / "plans").mkdir(exist_ok=True)
    (worktree / "plans" / "LEAD").write_text(lead + "\n")
    (worktree / "plans" / "CURRENT_PLAN").write_text(parts[1] + "\n")
    common = Path(run("git", "rev-parse", "--git-common-dir", cwd=worktree).strip())
    exclude = (common if common.is_absolute() else worktree / common) / "info" / "exclude"
    for name in ("plans/LEAD", "plans/CURRENT_PLAN"):
        if subprocess.run(["git", "check-ignore", "-q", name], cwd=worktree).returncode != 0:
            exclude.parent.mkdir(parents=True, exist_ok=True)
            with exclude.open("a") as f:
                f.write(name + "\n")


def start(repo: Path, slot: str, argv: list[str], prompt: str) -> dict:
    need("hal2-cli-git")
    command = ["hal2-cli-git", "worktree", "run", slot, "--agent", arg(argv, "--agent") or "claude",
               "--detach", "--json"]
    if "--tmux" in argv:
        command.append("--tmux")
    if arg(argv, "--model"):
        command += ["--model", arg(argv, "--model")]
    command += ["--prompt", prompt]
    env = {k: v for k, v in os.environ.items() if k not in DROPPED_ENV}
    shell = os.environ.get("SHELL") or "/bin/zsh"
    r = subprocess.run([shell, "-lc", "exec " + shlex.join(command)], cwd=repo, env=env, stdin=subprocess.DEVNULL,
                       capture_output=True, text=True)
    if r.returncode != 0:
        die(f"hal2-cli-git worktree run {slot} failed: {(r.stderr + r.stdout).strip()}")
    for line in reversed(r.stdout.splitlines()):
        try:
            return json.loads(line)
        except ValueError:
            continue
    die(f"hal2-cli-git worktree run {slot} printed no report: {r.stdout.strip()}")


def first_prompt(prompt: str | None, exact: bool) -> str:
    if exact and prompt:
        return prompt
    return f"Run /mfm (merge-from-main) first, then:\n\n{prompt}" if prompt else "/mfm"


def arg(argv: list[str], flag: str) -> str | None:
    return argv[argv.index(flag) + 1] if flag in argv and argv.index(flag) + 1 < len(argv) else None


def main(argv: list[str]) -> int:
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    repo = main_checkout(Path(arg(argv, "--repo") or ".").expanduser().resolve())
    first, base, lead = arg(argv, "--from") or "1", arg(argv, "--base"), arg(argv, "--lead")
    if not first.isdigit() or not 1 <= int(first) <= 99:
        die(f"--from needs a slot from 01 to 99, not '{first}'")
    if lead:
        lead_parts(lead)
    slot, skipped, entry = choose(repo, int(first), base)
    prepare(repo, slot, entry, base, float(arg(argv, "--min-free-gb") or 50))
    if lead:  # the marker before the start: the subservant never runs unmarked
        write_lead(Path(entry["path"]) if entry else create_worktree(repo, slot), lead)
    report = start(repo, slot, argv, first_prompt(arg(argv, "--prompt"), "--exact" in argv or bool(lead)))
    result = {
        "repo": repo.name,
        "slot": report.get("slot") or slot,
        "pane": report.get("pane"),
        "mode": report.get("mode"),
        "worktree": report.get("worktree"),
        "attach": f"hal2-cli-agents attach {repo.name}/{slot}",
        "skipped": skipped,
        "base": base,
        "lead": lead,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

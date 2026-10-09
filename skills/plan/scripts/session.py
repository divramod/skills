"""The running agent session's model and effort, and whether the next step needs a switch to its own.

A step's `Model` and `Effort` hold only when the session switches before it (SKILL.md "Model and effort per step");
hal2 plan 0214's field test saw a plan run two sonnet rows on opus because nothing checked them. So `plan.py
current` and `plan.py status <n> next` compare the next step with the session and name the switch in `switch`.

The session is the nearest `claude` process above this script: its `--model`/`--effort` flags (hal2's `switch`
and `worktree run` pass them), else `~/.claude/settings.json`'s `model` and the model's `modelSettings` effort.
Models compare by family (`opus`, `opus[1m]` and `claude-opus-5-5` are one), efforts as written. Another agent or
no claude process above: nothing is known and no switch is named.
"""
import json
import subprocess
from pathlib import Path

FAMILIES = ("fable", "opus", "sonnet", "haiku")


def family(model: str) -> str:
    """`opus` for `opus`, `opus[1m]` and `claude-opus-5-5`; the lowercased name for anything else."""
    name = model.strip().lower()
    return next((f for f in FAMILIES if f in name), name)


def process(pid: int) -> tuple[int, str] | None:
    """(parent pid, command line) of a process, None when it is gone."""
    out = subprocess.run(["ps", "-o", "ppid=,args=", "-p", str(pid)], capture_output=True, text=True)
    parts = out.stdout.strip().split(None, 1)
    if out.returncode or len(parts) < 2:
        return None
    return int(parts[0]), parts[1]


def claude_args(start: int, lookup=process) -> list[str] | None:
    """The argument list of the nearest `claude` process from `start` upwards, None without one."""
    pid, seen = start, set()
    while pid > 1 and pid not in seen:
        seen.add(pid)
        found = lookup(pid)
        if not found:
            return None
        parent, args = found
        words = args.split()
        if words and Path(words[0]).name == "claude":
            return words[1:]
        pid = parent
    return None


def flag(args: list[str], name: str) -> str:
    for i, word in enumerate(args):
        if word == "--":
            break
        if word == name and i + 1 < len(args):
            return args[i + 1]
        if word.startswith(name + "="):
            return word.split("=", 1)[1]
    return ""


def settings_defaults(settings: Path) -> tuple[str, str]:
    """(model, effort) a session without flags starts on."""
    try:
        data = json.loads(settings.read_text())
    except (OSError, ValueError):
        return "", ""
    model = str(data.get("model") or "")
    per_model = data.get("modelSettings") or {}
    effort = next((str(v.get("effortLevel") or "") for k, v in per_model.items()
                   if model and family(k) == family(model) and isinstance(v, dict)), "")
    return model, effort or str(data.get("effortLevel") or "")


def current(start: int, settings: Path, lookup=process) -> dict | None:
    """{"model", "effort"} of the running Claude Code session, None when this is no Claude Code session."""
    args = claude_args(start, lookup)
    if args is None:
        return None
    model, effort = settings_defaults(settings)
    return {"model": flag(args, "--model") or model, "effort": flag(args, "--effort") or effort}


def switch_for(step: dict | None, session: dict | None) -> dict | None:
    """{"model", "effort", "from"} when the step's model or effort differs from the session's, else None."""
    if not step or not session:
        return None
    model, effort = step.get("model", ""), step.get("effort", "")
    differs = (model and session["model"] and family(model) != family(session["model"])) or \
        (effort and session["effort"] and effort.lower() != session["effort"].lower())
    if not differs:
        return None
    return {"model": model or session["model"], "effort": effort or session["effort"], "from": session}

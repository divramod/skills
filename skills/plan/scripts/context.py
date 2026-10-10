#!/usr/bin/env python3
"""How full the agent's context window is, to decide whether a running plan stops for a handoff.

  context.py [--threshold <percent>] [--window <tokens>] [--session <id>] [--transcript <file>]

Claude Code: the session is $CLAUDE_CODE_SESSION_ID, its transcript ~/.claude/projects/*/<session>.jsonl.
Used tokens are the last main-conversation API call's input (uncached + cache read + cache write) plus its
output, which is what the next call starts from. The window comes from --window, else $CLAUDE_CONTEXT_WINDOW,
else the session's model: the last `/model` switch in its transcript ("Set model to `Opus 5.5 (1M context)`"),
else the `--model` of the `claude` process running this script (hal2 starts sessions with `--model opus[1m]`),
else $ANTHROPIC_MODEL, else the model setting in ~/.claude/settings.json; 1,000,000 for a 1M model (`[1m]`,
"1M context"), else 200,000. When more tokens are in use than that, the window must be the 1M one.

`percent` is measured against the usable window, i.e. without Claude Code's auto-compact buffer (16.5% of the
window), exactly like the Claude Code statusline shows it; `raw_percent` is against the whole window.

The threshold is --threshold, else hal2's `[autoclear]` settings (`hal2-cli-agents settings --json`, agents.toml):
`step_percent` when it is set (`step_tokens`: the plan runs this check at a step boundary, where a clear is cheapest,
so it stops earlier there than the guard's ceiling does mid-step; hal2 research 0048), else `percent` (the ceiling,
the lower of `percent` and `tokens`), else 35. `autoclear` says whether the session can clear and continue on its own after a hand-off
(`hal2-cli-agents clear-and-continue --detach`): hal2's autoclear is enabled and the agent is Claude Code in a tmux
pane or a hal2 terminal host ($CLAUDE_CODE_SESSION_ID, and $TMUX_PANE or $HAL2_TERMINAL: clear-and-continue takes
the pane `%<n>` or `t:<id>` from them itself); `autoclear_reason` says why not. $HAL2_CLI_AGENTS names the program
(default `hal2-cli-agents` on the PATH).

Prints JSON: {"known", "used", "window", "percent", "raw_percent", "threshold", "stop", "source", "autoclear",
"autoclear_reason", "model_source"}. `model_source` says where the window's model came from. `stop` is true when percent >= threshold. When nothing can be measured (another agent, no transcript yet) `known` is false and
`stop` is null: the agent judges for itself. Always exits 0 unless the arguments are wrong.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_WINDOW = 200_000
LARGE_WINDOW = 1_000_000
DEFAULT_THRESHOLD = 35.0
# Share of the window Claude Code keeps free for auto-compaction; the statusline leaves it out.
AUTO_COMPACT_BUFFER = 0.165
MODEL_SWITCH = re.compile(r"<local-command-stdout>Set model to (.+?)(?: and saved|</local-command-stdout>)")


def find_transcript(session: str, projects: Path) -> Path | None:
    matches = sorted(projects.glob(f"*/{session}.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def last_usage(transcript: Path) -> tuple[int | None, str | None]:
    """Tokens in context after the last main-chain assistant message (None when there is none), and the model
    the session's last `/model` switch set (None without one)."""
    used, model = None, None
    with transcript.open(encoding="utf-8", errors="replace") as lines:
        for line in lines:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("isSidechain"):
                continue
            if entry.get("type") == "user":
                content = (entry.get("message") or {}).get("content")
                switch = MODEL_SWITCH.search(content) if isinstance(content, str) else None
                if switch:
                    model = switch.group(1).strip("` ")
                continue
            if entry.get("type") != "assistant":
                continue
            usage = (entry.get("message") or {}).get("usage")
            if not usage:
                continue
            used = sum(int(usage.get(key) or 0) for key in (
                "input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "output_tokens"))
    return used, model


def process_model() -> str | None:
    """The `--model` of the nearest `claude` process above this one, None when there is none or it has none."""
    if not shutil.which("ps"):
        return None
    try:
        out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,args="], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    table = {}
    for line in out.stdout.splitlines():
        fields = line.split(None, 2)
        if len(fields) == 3 and fields[0].isdigit() and fields[1].isdigit():
            table[int(fields[0])] = (int(fields[1]), fields[2].split())
    pid, seen = os.getpid(), set()
    while pid in table and pid not in seen:
        seen.add(pid)
        ppid, args = table[pid]
        if any(Path(arg).name == "claude" for arg in args[:2]):
            for i, arg in enumerate(args):
                if arg == "--model" and i + 1 < len(args):
                    return args[i + 1]
                if arg.startswith("--model="):
                    return arg.split("=", 1)[1]
            return None
        pid = ppid
    return None


def session_model(switched: str | None, settings: Path) -> tuple[str, str]:
    """The session's model and where it came from, by Claude Code's precedence."""
    if switched:
        return switched, "/model in the transcript"
    model = process_model()
    if model:
        return model, "the session process's --model"
    env = os.environ.get("ANTHROPIC_MODEL", "").strip()
    if env:
        return env, "$ANTHROPIC_MODEL"
    try:
        return str(json.loads(settings.read_text()).get("model", "")), str(settings)
    except (OSError, json.JSONDecodeError, AttributeError):
        return "", "default"


def configured_window(model: str) -> int:
    env = os.environ.get("CLAUDE_CONTEXT_WINDOW", "").strip()
    if env.isdigit():
        return int(env)
    model = model.lower()
    return LARGE_WINDOW if model.endswith("[1m]") or "1m context" in model else DEFAULT_WINDOW


def autoclear_settings() -> tuple[dict | None, str]:
    """hal2's `[autoclear]` settings and the program, or None and why not."""
    program = os.environ.get("HAL2_CLI_AGENTS") or shutil.which("hal2-cli-agents")
    if not program:
        return None, "hal2-cli-agents is not installed"
    try:
        out = subprocess.run([program, "settings", "--json"], capture_output=True, text=True, timeout=10)
        settings = json.loads(out.stdout).get("autoclear") if out.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, AttributeError):
        settings = None
    if not isinstance(settings, dict):
        return None, f"{program} settings --json has no autoclear settings (hal2 too old?)"
    return settings, ""


def autoclear(settings: dict | None, why: str) -> tuple[bool, str]:
    if settings is None:
        return False, why
    if not settings.get("enabled", True):
        return False, "autoclear is disabled in agents.toml"
    if not os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip():
        return False, "not Claude Code ($CLAUDE_CODE_SESSION_ID unset)"
    if not agent_pane():
        return False, "not in a tmux pane or hal2 terminal ($TMUX_PANE and $HAL2_TERMINAL unset)"
    return True, ""


def agent_pane() -> str:
    """The agent's address as hal2 names it: `$TMUX_PANE` (`%<n>`), else `t:$HAL2_TERMINAL`; "" outside both."""
    pane = os.environ.get("TMUX_PANE", "").strip()
    if pane:
        return pane
    terminal = os.environ.get("HAL2_TERMINAL", "").strip()
    return f"t:{terminal}" if terminal else ""


def measure(args: argparse.Namespace, home: Path) -> dict:
    settings, why = autoclear_settings()
    threshold = args.threshold
    if threshold is None:
        numbers = [(settings or {}).get(key) for key in ("step_percent", "percent")]
        numbers = [float(n) for n in numbers if isinstance(n, (int, float)) and not isinstance(n, bool)]
        threshold = numbers[0] if numbers else DEFAULT_THRESHOLD
    can_clear, clear_why = autoclear(settings, why)
    result = {"known": False, "used": None, "window": None, "percent": None, "raw_percent": None,
              "threshold": threshold, "stop": None, "source": None,
              "autoclear": can_clear, "autoclear_reason": clear_why, "model_source": None}
    transcript = Path(args.transcript) if args.transcript else None
    if transcript is None:
        session = args.session or os.environ.get("CLAUDE_CODE_SESSION_ID", "")
        if not session:
            result["source"] = "no session id ($CLAUDE_CODE_SESSION_ID unset)"
            return result
        transcript = find_transcript(session, home / ".claude" / "projects")
        if transcript is None:
            result["source"] = f"no transcript for session {session}"
            return result
    try:
        used, switched = last_usage(transcript)
    except OSError as error:
        result["source"] = f"cannot read {transcript}: {error}"
        return result
    if used is None:
        result["source"] = f"no usage recorded yet in {transcript}"
        return result
    if args.window:
        window = args.window
    else:
        model, result["model_source"] = session_model(switched, home / ".claude" / "settings.json")
        window = configured_window(model)
    if used > window:
        window = max(window, LARGE_WINDOW)
    percent = round(min(100.0, 100 * used / (window * (1 - AUTO_COMPACT_BUFFER))), 1)
    result.update(known=True, used=used, window=window, percent=percent,
                  raw_percent=round(100 * used / window, 1),
                  stop=percent >= threshold, source=str(transcript))
    return result


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--threshold", type=float,
                        help="stop at this percent used (default: hal2's autoclear percent, else 35)")
    parser.add_argument("--window", type=int, help="context window size in tokens")
    parser.add_argument("--session", help="Claude Code session id (default: $CLAUDE_CODE_SESSION_ID)")
    parser.add_argument("--transcript", help="transcript file to read instead of finding it")
    args = parser.parse_args(argv)
    home = Path(os.environ.get("HOME", str(Path.home())))
    print(json.dumps(measure(args, home)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

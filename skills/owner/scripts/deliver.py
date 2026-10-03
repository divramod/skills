"""Templated messages to agent sessions without a model: typed into an idle session's empty prompt.

`send(pane, text)` types only when hal2 lists the agent in a resting state and its prompt box holds no draft
(no text typed by a person; the dim suggestion Claude Code shows there is no draft). Otherwise it refuses and the
tick hands the message to the woken owner session as a relay (Claude Code's SendMessage queues for busy sessions).
The prompt check follows hal2-agents' `scrape::claude_input`.
"""

import json
import re
import subprocess

READY = {"idle", "done", "sleeping"}
RULE = re.compile(r"^\s*─{8,}\s*$")
DIM = re.compile(r"\x1b\[2m.*?(?:\x1b\[(?:0|22)?m|$)")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def cli(*args: str, timeout: int = 30) -> tuple[int, str]:
    try:
        p = subprocess.run(["hal2-cli-agents", *args], capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, str(e)


def prompt_text(styled: str) -> str | None:
    """The text in Claude Code's input box (the last `❯` line between two rules), dim suggestions dropped;
    None when the screen shows no input box (a dialog, a menu, a screen hal2 cannot read)."""
    lines = styled.splitlines()
    rules = [i for i, line in enumerate(lines) if RULE.match(ANSI.sub("", line))]
    for top, bottom in reversed(list(zip(rules, rules[1:]))):
        box = [ANSI.sub("", DIM.sub("", line)) for line in lines[top + 1:bottom]]
        if box and box[0].lstrip().startswith("❯"):
            first = box[0].lstrip()[1:].strip()
            return "\n".join([first, *(line.strip() for line in box[1:])]).strip()
    return None


def agent(pane: str) -> dict | None:
    code, out = cli("list", "--json")
    try:
        data = json.loads(out) if code == 0 else {}
    except json.JSONDecodeError:
        return None
    rows = data.get("list", []) if isinstance(data, dict) else data
    return next((a for a in rows if a.get("pane_id") == pane), None)


def ready(pane: str) -> str | None:
    """None when a message may be typed into `pane` now, else why not."""
    a = agent(pane)
    if a is None:
        return "no agent in that pane"
    if a.get("state") not in READY:
        return f"agent is {a.get('state')}"
    code, screen = cli("capture", pane, "--styled")
    if code:
        return "capture failed"
    text = prompt_text(screen)
    if text is None:
        return "no empty input box on screen (a dialog or menu)"
    return f"a draft in the prompt: {text[:40]!r}" if text else None


def send(pane: str, text: str) -> str | None:
    """Type `text` and Enter into the agent at `pane`. None when sent, else why it was not."""
    why = ready(pane)
    if why:
        return why
    if cli("send", pane, text, "--paste")[0] or cli("send", pane, "enter", "--key")[0]:
        return "hal2-cli-agents send failed"
    return None

"""Templated messages to agent sessions without a model: typed into an idle session's empty prompt.

`send(pane, text)` types only when hal2 lists the agent in a resting state and its prompt box holds no draft
(no text typed by a person; the dim suggestion Claude Code shows there is no draft): hal2's own rule,
`hal2-cli-agents send --if-empty` (hal2 plan 0125), which exits 3 with the reason (busy, dialog, draft, no-agent)
and types nothing. Then the tick hands the message to the woken farmer session as a relay (Claude Code's
SendMessage queues for busy sessions).
"""

import json
import subprocess

READY = {"idle", "done", "sleeping"}
REFUSED = 3


def cli(*args: str, timeout: int = 30) -> tuple[int, str]:
    code, out, _ = run(*args, timeout=timeout)
    return code, out


def run(*args: str, timeout: int = 30) -> tuple[int, str, str]:
    try:
        p = subprocess.run(["hal2-cli-agents", *args], capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, "", str(e)


def agent(pane: str) -> dict | None:
    code, out = cli("list", "--json")
    try:
        data = json.loads(out) if code == 0 else {}
    except json.JSONDecodeError:
        return None
    rows = data.get("list", []) if isinstance(data, dict) else data
    return next((a for a in rows if a.get("pane_id") == pane), None)


def if_empty(pane: str, text: str, states: set[str] = READY) -> list[str]:
    """The arguments of a send that types `text` only into a resting agent with an empty box; `states` beyond
    the resting ones are allowed with --allow-state."""
    extra = [arg for state in sorted(set(states) - READY) for arg in ("--allow-state", state)]
    return ["send", pane, text, "--paste", "--if-empty", *extra]


def refusal(stderr: str) -> str:
    """hal2's reason from a refused send's stderr (`... not sent: draft: the input box holds ...`)."""
    return stderr.strip().split("not sent: ", 1)[-1] or "refused"


def send(pane: str, text: str, states: set[str] = READY) -> str | None:
    """Type `text` and Enter into the agent at `pane`. None when sent, else why it was not."""
    code, _, err = run(*if_empty(pane, text, states))
    if code == REFUSED:
        return refusal(err)
    if code or cli("send", pane, "enter", "--key")[0]:
        return "hal2-cli-agents send failed"
    return None

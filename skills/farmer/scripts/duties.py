"""The development lead's, ci's, watch's and autoclear's rules as code (plan 0007 step 3).

Each `<duty>(item, ctx)` scans read-only and plans actions (see tick.py). Templated help is typed into idle
sessions; what needs judgment (a question, a permission prompt, a real CI failure, an unclear stop) becomes a
`wake` item with its evidence. Keys keep a round from repeating what an earlier one did.
"""

import datetime as dt
import re
import sys
from pathlib import Path

import ci_scan
import lead_scan
from tick import act

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parents[1]
sys.path.insert(0, str(SKILLS / "sanity-watch" / "scripts"))
sys.path.insert(0, str(SKILLS / "fix-autoclear" / "scripts"))
import evidence  # noqa: E402  (fix-autoclear)
import scan as watch_scan  # noqa: E402  (sanity-watch)

LEAD = "farmer (development lead)"
TEXT = {
    "no-plan": LEAD + ": write your task into plans/CURRENT_PLAN now: the plan's <NNNN>-<slug>, the shot's "
                      "<shotfile>/<n>/<title-slug>, or a short kebab-case task name (global CLAUDE.md).",
    "context-high": LEAD + ": your context is at {percent}%. Run /handoff now; hal2's autoclear continues you.",
    "continue": LEAD + ": you stopped mid-plan ({plan}). Continue the plan to its end.",
    "failed": "Your last turn failed ({why}). Check git status and your last tool result, then continue.",
    "resume": "Your last response was cut off ({error}). Check git status and the result of your last tool call, "
              "then continue where you stopped.",
    "slot-red": "farmer (ci): your branch's CI is red: {workflow} ({jobs}) {url}. Fix it in your plan.",
}
# A last message that just announces the next step: the session stopped by accident, not to wait.
GOING_ON = re.compile(r"\b(next,? I'?ll|now I'?ll|I'?ll now|moving on to|continuing with)\b", re.I)
WAITS = re.compile(r"\b(wait|waiting|once|when it|until|your go|you decide|\?)", re.I)
# CI failures that a rerun fixes: the network, a registry, a lost runner, a cancelled job.
TRANSIENT = re.compile(r"ECONNRESET|ETIMEDOUT|EAI_AGAIN|Could not resolve host|TLS handshake timeout|"
                       r"connection (reset|refused|timed out)|50[234] (Bad Gateway|Service Unavailable|Gateway)|"
                       r"rate limit|The runner has received a shutdown signal|lost communication with the server|"
                       r"The operation was canceled|toomanyrequests", re.I)
DAY = dt.timedelta(days=1)


def plan_lead(item: dict, ctx: dict, scan: dict | None = None) -> list[dict]:
    scan = scan if scan is not None else lead_scan.scan(ctx["top"], False)
    out = []
    for n in scan.get("needs_help", []):
        kind, slot, pane = n["kind"], n.get("slot") or "-", n.get("pane")
        if slot in ctx.get("told", set()):
            continue
        key, done = f"lead:{n['session']}:{n['since']}", [sys.executable, str(HERE / "lead_scan.py"), "record",
                                                           n["session"], str(n["since"])]
        said = (n.get("said") or "").strip().split("\n\n")[-1]
        text = None
        if kind == "no-plan":
            text = TEXT["no-plan"]
        elif kind == "context-high":
            text = TEXT["context-high"].format(percent=n.get("context_percent"))
        elif kind == "idle-in-plan" and GOING_ON.search(said) and not WAITS.search(said):
            text = TEXT["continue"].format(plan=n.get("plan") or "your plan")
        elif kind == "failed" and "watch" not in ctx.get("duties", ()):
            text = TEXT["failed"].format(why=n.get("why", "failed"))
        if text is None:
            out.append(act("lead", kind, "wake", slot, key=key, text=f"{kind}: {n.get('why', '')}", evidence=n))
            continue
        out.append(act("lead", kind, "send", slot, pane=pane, text=text, key=key))
        out.append(act("lead", "handled", "run", slot, argv=done + [kind, "--repo", ctx["top"]], text=f"{kind} handled",
                       after=key))
    return out


def plan_ci(item: dict, ctx: dict, scan: dict | None = None, log_failed=None) -> list[dict]:
    scan = scan if scan is not None else ci_scan.scan(ctx["top"], False)
    log_failed = log_failed or (lambda run: ci_scan.run(["gh", "run", "view", str(run), "--log-failed"], ctx["main"]))
    out, slots = [], set(ctx.get("panes", {}))
    for f in scan.get("findings", []):
        kind, run, key = f["kind"], f["run"], f"ci:{f['run']}"
        record = [sys.executable, str(HERE / "ci_scan.py"), "record", str(run)]
        if kind == "main-red":
            tail = (log_failed(run) or "")[-20000:]
            transient = TRANSIENT.search(tail)
            if transient:
                out.append(act("ci", "rerun", "run", "-", key=key, argv=["gh", "run", "rerun", str(run), "--failed"],
                               text=f"reran {f['workflow']} (transient: {transient.group(0)})"))
                out.append(act("ci", "handled", "run", "-", argv=record + ["rerun --failed", "--repo", ctx["top"]],
                               after=key))
            else:
                out.append(act("ci", "main-red", "delegate", "-", key=key, text=f"main is red: {f['why']}",
                               brief={"finding": f, "log_tail": tail[-4000:]}))
        elif kind == "slot-red" and f["branch"] in slots:
            text = TEXT["slot-red"].format(workflow=f["workflow"], jobs=", ".join(f.get("failed_jobs", [])), url=f["url"])
            out.append(act("ci", kind, "send", f["branch"], pane=ctx["panes"][f["branch"]], text=text, key=key))
            out.append(act("ci", "handled", "run", f["branch"], argv=record + ["told the slot", "--repo", ctx["top"]],
                           after=key))
        else:
            out.append(act("ci", kind, "wake", f.get("branch") or "-", key=key, text=f["why"], evidence=f))
    return out


def plan_watch(item: dict, ctx: dict, incidents: list[dict] | None = None) -> list[dict]:
    if incidents is None:
        state, at = watch_scan.load_state(), watch_scan.now_ms()
        agents = watch_scan.run_json("hal2-cli-agents", "list", "--json", default=[]) or []
        orphans = watch_scan.run_json("hal2-cli-agents", "terminal", "orphans", "--json", default=[]) or []
        events = watch_scan.chronicle_events(at - 24 * 3600 * 1000)
        found = watch_scan.find_incidents(ctx["main"], agents, events, orphans, state, at)
        incidents = [i for i in found if i["id"] not in state.get("handled", {})]
    out = []
    for i in incidents:
        slot, action = i.get("slot") or "-", i["action"]
        record = [sys.executable, str(SKILLS / "sanity-watch/scripts/scan.py"), "record", i["id"]]
        landing = slot in ctx.get("landing", set())
        if action == "resume" and i.get("pane") and not landing:
            error = (i["evidence"].get("api_error") or {}).get("text") or i["name"]
            out.append(act("watch", "resume", "send", slot, pane=i["pane"], states=["failed"], key=f"watch:{i['id']}",
                           text=TEXT["resume"].format(error=error[:160])))
            out.append(act("watch", "handled", "run", slot, argv=record + ["resume", "--session", i["session"]],
                           after=f"watch:{i['id']}"))
        elif action == "count":
            out.append(act("watch", "handled", "run", slot, argv=record + ["count", "--note", i.get("reason", "")]))
        elif action in ("escalate", "handover"):
            out.append(act("watch", action, "notify", slot, key=f"watch:{i['id']}",
                           text=f"sanity-watch: {slot} {i['name']}: {i.get('reason') or action}"))
            out.append(act("watch", "handled", "run", slot, argv=record + [action], after=f"watch:{i['id']}"))
        elif action != "wait":
            out.append(act("watch", action, "wake", slot, key=f"watch:{i['id']}", text=f"{i['class']} {i['name']}",
                           evidence=i))
    return out


def plan_autoclear(item: dict, ctx: dict, problems: list[dict] | None = None) -> list[dict]:
    problems = problems if problems is not None else evidence.doctor_items(1.5)
    out, agents = [], ctx.get("agents_by_pane", {})
    for p in problems:
        a = agents.get(p.get("pane")) or {}
        slot = a.get("slot") or "-"
        if p.get("session") and a.get("session_id") == p["session"] and a.get("state") in ("idle", "done", "sleeping"):
            out.append(act("autoclear", "continue", "run", slot, key=f"autoclear:{p['session']}",
                           argv=["hal2-cli-agents", "clear-and-continue", "--pane", p["pane"], "--session",
                                 p["session"], "--await-handoff", "--detach"],
                           text=f"clear-and-continue for {p['who']} (autoclear {p.get('reason') or 'gave up'})"))
        reason = p.get("reason") or "attempts"
        out.append(act("autoclear", "fix", "delegate", slot, key=f"autoclear-fix:{reason}",
                       text=f"/fix-autoclear {slot}: {p.get('message') or reason}", brief={"problem": p}))
    return out

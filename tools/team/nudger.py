#!/usr/bin/env python3
"""Keeps the team moving without any session having to remember to: every minute it asks herdr which sessions sit
idle, and prompts each in-flight session that has been idle too long with a fixed line.

The owner, 2026-10-21, after the team stalled again: "(the owner's words)". flow_wait
only woke the coordinator, an LLM that had to re-arm it and act; a compact or a dialog stopped the chain. This runs
detached (pid file), reads herdr's own agent state, and needs no model to decide. A session on a dialog (blocked) is
the owner's: it shows a notification instead of typing into it.

  nudger.py            loop forever (start detached: nohup python3 nudger.py > nudger.log 2>&1 & echo $! > nudger.pid)
  nudger.py --once     one pass, print what it would do and do it
"""
import json
import os
import subprocess
import sys
import time

BEADS = os.path.expanduser("~/.agent-board")
IN_FLIGHT = os.path.join(BEADS, "in_flight.json")
STATE = os.path.join(BEADS, "nudger-state.json")
IDLE_BEFORE_NUDGE_S = 10 * 60
NUDGE_COOLDOWN_S = 20 * 60
ALWAYS_WATCHED = ("agent-coordinator",)
DIALOG_MARKERS = ("↑/↓ choose", "esc not now", "Enter to confirm", "Do you want to proceed")
NUDGE = ("NUDGE (automatic, nudger.py): you have been idle {minutes} min while your task is in flight: {bead}. "
         "Do the next step now. If you are waiting on another session or the owner, post ONE line on your bead "
         "starting BLOCKED: with who and what, and tell agent-coordinator. Never end a turn on a plan.")


def herdr_agents() -> dict:
    out = subprocess.run(["herdr", "agent", "list"], capture_output=True, text=True).stdout
    result = json.loads(out)["result"]
    agents = result.get("agents", result) if isinstance(result, dict) else result
    # A session renames its terminal title to its task, so herdr's agent name is matched as well.
    by_title = {a.get("terminal_title_stripped") or a.get("name"): a for a in agents if a.get("pane_id")}
    return {**by_title, **{a["name"]: a for a in agents if a.get("pane_id") and a.get("name")}}


def watched_sessions() -> dict:
    try:
        tasks = json.load(open(IN_FLIGHT))["tasks"]
    except (OSError, ValueError, KeyError):
        tasks = []
    watched = {name: "coordination of the in-flight tasks" for name in ALWAYS_WATCHED} if tasks else {}
    for task in tasks:
        for session in task["sessions"]:
            watched[session] = task["bead"]
    return watched


def on_a_dialog(pane: str) -> bool:
    # herdr reports a Claude choice dialog (autocompact, permission) as idle; typing into it would pick an option.
    screen = subprocess.run(["herdr", "pane", "read", pane, "--source", "visible"], capture_output=True, text=True).stdout
    return any(marker in screen for marker in DIALOG_MARKERS)


def decide(watched: dict, agents: dict, state: dict, now: float, on_a_dialog=on_a_dialog) -> list:
    """Returns (action, session, pane, text) tuples and updates state in place."""
    actions = []
    for session, bead in watched.items():
        agent = agents.get(session)
        entry = state.setdefault(session, {})
        status = agent.get("agent_status") if agent else None
        if status not in ("idle", "done", "blocked"):
            entry.pop("idle_since", None)
            continue
        idle_since = entry.setdefault("idle_since", now)
        if now - idle_since < IDLE_BEFORE_NUDGE_S or now - entry.get("last_nudge", float("-inf")) < NUDGE_COOLDOWN_S:
            continue
        entry["last_nudge"] = now
        minutes = round((now - idle_since) / 60)
        if status == "blocked" or on_a_dialog(agent["pane_id"]):
            actions.append(("notify", session, agent["pane_id"], f"{session} is waiting on a dialog ({minutes} min)"))
        else:
            actions.append(("prompt", session, agent["pane_id"], NUDGE.format(minutes=minutes, bead=bead)))
    return actions


def act(actions: list) -> None:
    for kind, session, pane, text in actions:
        print(time.strftime("%H:%M:%S"), kind, session, text[:80], flush=True)
        if kind == "prompt":
            subprocess.run(["herdr", "agent", "prompt", pane, text], capture_output=True)
        else:
            subprocess.run(["herdr", "notification", "show", "the project team", "--body", text, "--sound", "request"],
                           capture_output=True)


def one_pass() -> None:
    try:
        state = json.load(open(STATE))
    except (OSError, ValueError):
        state = {}
    act(decide(watched_sessions(), herdr_agents(), state, time.time()))
    with open(STATE + ".new", "w") as f:
        json.dump(state, f)
    os.replace(STATE + ".new", STATE)


if __name__ == "__main__":
    if "--once" in sys.argv:
        one_pass()
    else:
        while True:
            try:
                one_pass()
            except Exception as error:  # ponytail: a herdr hiccup must not kill the loop; it retries next minute
                print("error", error, flush=True)
            time.sleep(60)

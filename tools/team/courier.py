#!/usr/bin/env python3
"""Keeps the team moving with no model deciding: once a minute it asks herdr which sessions sit idle, then

- hands an idle session that holds nothing its next queued ticket (task_queue.py hand) with one fixed line;
- nudges an idle session that holds a ticket once it has been idle `idle_minutes`, at most every `cooldown_minutes`;
- shows a notification instead when the session sits on a dialog, since typing would pick an option.

  courier.py           loop forever (start detached; the pid file is courier.pid in the board folder)
  courier.py --once    one pass
"""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import suite_config  # noqa: E402
import task_queue  # noqa: E402

HAND = "Next from the queue: {bead}. Read it (bd show {bead}), claim it and start."
NUDGE = "Idle {minutes} min with {bead} in flight. Go on with it, or say what blocks it (BLOCKED to the coordinator)."
DIALOG_MARKERS = ("Do you want to", "Enter to confirm", "Esc to cancel", "❯ 1.")


def herdr_agents() -> dict:
    out = subprocess.run(["herdr", "agent", "list"], capture_output=True, text=True).stdout
    result = json.loads(out)["result"]
    agents = result.get("agents", result) if isinstance(result, dict) else result
    return {a["name"]: a for a in agents if a.get("pane_id") and a.get("name")}


def on_a_dialog(pane: str) -> bool:
    screen = subprocess.run(["herdr", "pane", "read", pane, "--source", "visible"], capture_output=True, text=True).stdout
    return any(marker in screen for marker in DIALOG_MARKERS)


def decide(board: dict, config: dict, agents: dict, state: dict, now: float, on_a_dialog=on_a_dialog) -> list:
    """Returns (kind, session, pane, text) tuples; hands tickets in `board` and updates `state` in place."""
    actions = []
    idle_s, cooldown_s = 60 * config["courier"]["idle_minutes"], 60 * config["courier"]["cooldown_minutes"]
    watched = {suite_config.session_name(config, role) for role in config["courier"]["always_watched"]} \
        if board["tasks"] else set()
    sessions = watched | {s for task in board["tasks"] for s in task["sessions"]} | {e["agent"] for e in board["queue"]}
    for session in sorted(sessions):
        agent = agents.get(session)
        entry = state.setdefault(session, {})
        if not agent or agent.get("agent_status") not in ("idle", "done", "blocked"):
            entry.pop("idle_since", None)
            continue
        idle_since = entry.setdefault("idle_since", now)
        dialog = agent.get("agent_status") == "blocked" or on_a_dialog(agent["pane_id"])
        held = task_queue.holder(board, session)
        if not held and not dialog:
            bead = task_queue.hand(board, session)
            if bead:
                actions.append(("prompt", session, agent["pane_id"], HAND.format(bead=bead)))
                entry.update(idle_since=now, last_nudge=now)
            continue
        if not held or now - idle_since < idle_s or now - entry.get("last_nudge", float("-inf")) < cooldown_s:
            continue
        entry["last_nudge"] = now
        minutes = round((now - idle_since) / 60)
        if dialog:
            actions.append(("notify", session, agent["pane_id"], f"{session} is waiting on a dialog ({minutes} min)"))
        else:
            actions.append(("prompt", session, agent["pane_id"], NUDGE.format(minutes=minutes, bead=held)))
    return actions


def act(actions: list) -> None:
    for kind, session, pane, text in actions:
        print(time.strftime("%H:%M:%S"), kind, session, text[:80], flush=True)
        if kind == "prompt":
            subprocess.run(["herdr", "agent", "prompt", pane, text], capture_output=True)
        else:
            subprocess.run(["herdr", "notification", "show", "team", "--body", text, "--sound", "request"],
                           capture_output=True)


def one_pass() -> None:
    config = suite_config.load()
    state_path = suite_config.board_path(config, "courier-state.json")
    try:
        state = json.loads(state_path.read_text())
    except (OSError, ValueError):
        state = {}
    agents = herdr_agents()
    with task_queue.locked(task_queue.in_flight_path(config)) as board:
        actions = decide(board, config, agents, state, time.time())
    act(actions)
    state_path.write_text(json.dumps(state))


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

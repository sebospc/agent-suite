#!/usr/bin/env python3
"""The team check: prints one line per finding and exits 1 when there is any, so a timer wakes the coordinator only
on a finding. Silent and exit 0 when the team is in order.

Findings: a session with more than one bead in progress; a bead in progress past `team_check.stale_hours` with no
update; a session with ready beads, nothing in progress and nothing in flight (idle with work); a task in flight
whose bead is closed; a slot held past twice its minutes. Sessions come from team.json.
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import slots  # noqa: E402
import suite_config  # noqa: E402
import task_queue  # noqa: E402


def bd(config: dict, *args) -> list:
    env = dict(os.environ, BEADS_ACTOR=suite_config.session_name(config, config["coordinator"]))
    out = subprocess.run(["bd", *args, "--json"], capture_output=True, text=True, env=env,
                         cwd=os.path.expanduser(config["board_dir"])).stdout
    return json.loads(out or "[]")


def team_sessions(config: dict) -> list:
    path = suite_config.board_path(config, config["team_json"])
    try:
        raw = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    return [suite_config.session_name(config, name) for name in raw.get("sessions", {})]


def hours_since(stamp: str, now: float) -> float:
    return (now - datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()) / 3600


def findings(config: dict, sessions: list, in_progress: list, ready: list, board: dict, closed: set,
             slot_board: dict, now: float) -> list:
    found = []
    for session in sessions:
        mine = [b for b in in_progress if b.get("assignee") == session]
        if len(mine) > 1:
            found.append(f"{session}: {len(mine)} beads in progress ({', '.join(b['id'] for b in mine)}); one at a time")
        for bead in mine:
            age = hours_since(bead.get("updated_at") or bead.get("created_at"), now)
            if age > config["team_check"]["stale_hours"]:
                found.append(f"{session}: {bead['id']} in progress, no update for {age:.0f} h")
        has_ready = any(b.get("assignee") == session for b in ready)
        if has_ready and not mine and not task_queue.holder(board, session):
            found.append(f"{session}: ready beads but nothing in progress or in flight")
    found += [f"in flight: {task['bead']} is closed; take it off (task_queue.py done)"
              for task in board["tasks"] if task["bead"] in closed]
    return found + [f"slot {line}" for line in slots.overdue(slot_board, now)]


def main() -> int:
    config = suite_config.load()
    board = task_queue.read(task_queue.in_flight_path(config))
    flying = [task["bead"] for task in board["tasks"]]
    closed = {b["id"] for b in bd(config, "show", *flying) if b.get("status") == "closed"} if flying else set()
    lines = findings(config, team_sessions(config), bd(config, "list", "--status", "in_progress"), bd(config, "ready"),
                     board, closed, task_queue.read(slots.slots_path(config), {}), time.time())
    for line in lines:
        print(line)
    return 1 if lines else 0


if __name__ == "__main__":
    sys.exit(main())

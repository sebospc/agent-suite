import time
from typing import List

from cockpit.controls.action import from_record
from cockpit.controls.commands import COMMANDS
from cockpit.display_time import clock_time


def midnight(now: float) -> float:
    return time.mktime(time.localtime(now)[:3] + (0, 0, 0, 0, 0, -1))


UNRESOLVED_S = 15 * 60  # a control's proof window; past it with no outcome logged, the cockpit stopped before its proof


def day_rows(records: List[dict], origin: str, now: float) -> List[dict]:
    """The controls one origin (the owner or the autopilot) sent, newest first, each with its proved outcome from the
    same log, or waiting; cut is the context a proved compaction removed."""
    mine = [r for r in records if r.get("origin") == origin]
    outcome = {r["id"]: r for r in mine if r.get("event") in ("done", "confirmed", "failed", "not_seen")}  # the last one wins
    rows = []
    for sent in (r for r in mine if r.get("event") == "sent"):
        end = outcome.get(sent["id"], {})
        command = COMMANDS.get(sent.get("kind", ""))
        untimed = command is not None and command.proof_window_s is None
        if untimed and end.get("event") == "not_seen":
            end = {}  # logged under the old 15-minute rule; its proof waits for the next turn now (brain's F2)
        proved = end.get("event") == "done" and end.get("pre") and end.get("post") is not None
        lost = not end and not untimed and now - sent["t"] > UNRESOLVED_S
        waits = command.awaited(from_record(sent)) if command and not end else ""  # a /model send waits for a turn, not a compaction (pg-97i4)
        rows.append({"t": clock_time(sent["t"]), "at": sent["t"], "id": sent["id"], "session": sent["session"], "kind": sent.get("kind", ""),
                     "text": sent.get("text", ""), "reason": sent.get("reason", ""),
                     "state": "not_seen" if lost else end.get("event", "waiting"),
                     "result": "No result logged: the cockpit stopped before its proof showed." if lost else end.get("text", waits),
                     "cut": end["pre"] - end["post"] if proved else None})
    return list(reversed(rows))
